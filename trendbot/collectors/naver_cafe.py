"""네이버 카페 인기글 수집기 (집 PC 전용).

- 자동 로그인은 하지 않습니다. 사용자가 집 PC의 'ㄷㅅㅂㄱ 네이버 로그인' 아이콘으로 연 전용 브라우저 창에서
  직접 로그인해 두면, 그 로그인 상태(쿠키)만 재사용합니다.
- 인기글 목록만 하루 1~2회 읽습니다. 본문은 열지 않습니다.
- 로그인이 풀렸으면 LoginRequired를 일으켜 상태 페이지에 "집 PC에서 네이버 로그인 필요"를 띄웁니다.
"""

from __future__ import annotations

import json
import re
from typing import Any

from trendbot.config import DATA_DIR
from trendbot.models import Post

PROFILE_DIR = DATA_DIR / "browser-profile"
POPULAR_URL = "https://cafe.naver.com/f-e/cafes/{cafe_id}/popular"


class LoginRequired(Exception):
    pass


def _context(pw, headless: bool = True):
    """로그인 상태가 저장된 전용 브라우저. 집 PC 도우미는 윈도우 기본 Edge를 씀 (TRENDBOT_BROWSER=msedge)."""
    import os
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    channel = os.environ.get("TRENDBOT_BROWSER") or None
    return pw.chromium.launch_persistent_context(str(PROFILE_DIR), headless=headless, locale="ko-KR", channel=channel)


def _walk_articles(obj: Any, out: list[dict]) -> None:
    """네이버 카페 응답(JSON) 어디에 있든 글 목록(subject + articleId)을 찾아냄."""
    if isinstance(obj, dict):
        if "articleId" in obj and ("subject" in obj or "title" in obj):
            out.append(obj)
        for v in obj.values():
            _walk_articles(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _walk_articles(v, out)


def articles_to_posts(payloads: list[Any], source: dict, cafe_id: str | int) -> list[Post]:
    found: list[dict] = []
    for p in payloads:
        _walk_articles(p, found)
    posts: list[Post] = []
    seen: set[str] = set()
    for a in found:
        aid = str(a["articleId"])
        if aid in seen:
            continue
        seen.add(aid)
        posts.append(
            Post(
                source_id=source["id"],
                title=" ".join(str(a.get("subject") or a.get("title")).split()),
                url=f"https://cafe.naver.com/f-e/cafes/{cafe_id}/articles/{aid}",
                rank=len(posts) + 1,
                views=a.get("readCount"),
                likes=a.get("likeItCount") or a.get("likeCount"),
                comments=a.get("commentCount"),
            )
        )
        if len(posts) >= 20:
            break
    return posts


def _find_cafe_id(html: str) -> str | None:
    for pat in (r"g_sClubId\s*=\s*\"?(\d+)", r"clubid=(\d+)", r"\"cafeId\"\s*:\s*(\d+)", r"/cafes/(\d+)"):
        m = re.search(pat, html, re.IGNORECASE)
        if m:
            return m.group(1)
    return None


def collect(source: dict, headless: bool = True) -> list[Post]:
    from playwright.sync_api import sync_playwright  # 집 PC에만 설치

    payloads: list[Any] = []
    with sync_playwright() as pw:
        ctx = _context(pw, headless)
        try:
            page = ctx.new_page()

            def on_response(resp):
                if "apis.naver.com" in resp.url and "json" in (resp.headers.get("content-type") or ""):
                    try:
                        payloads.append(resp.json())
                    except Exception:
                        pass

            page.on("response", on_response)
            page.goto(source["cafe_url"], wait_until="networkidle")
            cafe_id = source.get("cafe_id") or _find_cafe_id(page.content())
            if not cafe_id:
                raise RuntimeError("카페 번호를 찾지 못했습니다. sources.yaml에 cafe_id를 적어 주세요.")
            payloads.clear()
            page.goto(source.get("popular_url") or POPULAR_URL.format(cafe_id=cafe_id), wait_until="networkidle")
            page.wait_for_timeout(2000)
            if "nid.naver.com" in page.url:
                raise LoginRequired("네이버 로그인이 풀렸습니다. 집 PC 바탕화면의 'ㄷㅅㅂㄱ 네이버 로그인'을 눌러 다시 로그인해 주세요.")
            posts = articles_to_posts(payloads, source, cafe_id)
            if not posts:
                content = page.content()
                if "로그인" in content and ("멤버" in content or "가입" in content):
                    raise LoginRequired("카페 인기글을 볼 권한이 없습니다(로그인 또는 카페 가입 필요).")
            return posts
        finally:
            ctx.close()


def open_login_window() -> None:
    """사용자가 직접 로그인할 수 있도록 전용 브라우저 창을 엽니다. 창을 닫으면 끝납니다."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        ctx = _context(pw, headless=False)
        page = ctx.new_page()
        page.goto("https://nid.naver.com/nidlogin.login")
        print("열린 창에서 네이버에 직접 로그인하세요. ('로그인 상태 유지'를 체크하면 오래 유지됩니다)")
        print("로그인을 마친 뒤 브라우저 창을 닫으면 저장됩니다.")
        try:
            page.wait_for_event("close", timeout=0)
        except Exception:
            pass
        ctx.close()


def dump_debug(payloads: list[Any]) -> str:
    return json.dumps(payloads, ensure_ascii=False)[:200000]


def _find_key(obj: Any, key: str) -> Any:
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            r = _find_key(v, key)
            if r is not None:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = _find_key(v, key)
            if r is not None:
                return r
    return None


def fetch_originals(urls: list[str]) -> dict[str, dict]:
    """로그인된 전용 브라우저로 카페 글 본문·이미지·댓글을 읽음 (발행 카드의 글만)."""
    from bs4 import BeautifulSoup
    from playwright.sync_api import sync_playwright

    from trendbot.collectors.original import MAX_COMMENTS, MAX_IMAGES, _text

    out: dict[str, dict] = {}
    if not urls:
        return out
    with sync_playwright() as pw:
        ctx = _context(pw)
        try:
            page = ctx.new_page()
            for url in urls:
                payloads: list[Any] = []
                handler = lambda r: payloads.append(r) if "apis.naver.com" in r.url else None
                page.on("response", handler)
                try:
                    page.goto(url, wait_until="networkidle")
                    page.wait_for_timeout(1500)
                    data = []
                    for r in payloads:
                        try:
                            data.append(r.json())
                        except Exception:
                            pass
                    html = _find_key(data, "contentHtml") or ""
                    if "nid.naver.com" in page.url:
                        out[url] = {"status": "login", "body": "", "images": [], "comments": []}
                        continue
                    soup = BeautifulSoup(html, "html.parser")
                    images = [i.get("src") for i in soup.find_all("img") if i.get("src", "").startswith("http")][:MAX_IMAGES]
                    items = _find_key(data, "items") or []
                    comments = [{"text": str(c.get("content", ""))[:300], "likes": c.get("likeCount")}
                                for c in items if isinstance(c, dict) and c.get("content")]
                    comments.sort(key=lambda c: -(c["likes"] or 0))
                    body = _text(soup) if html else ""
                    out[url] = {"status": "ok" if body or images else "empty", "body": body[:4000],
                                "images": images, "comments": comments[:MAX_COMMENTS]}
                except Exception as e:
                    out[url] = {"status": "error", "body": "", "images": [], "comments": [], "note": e.__class__.__name__}
                finally:
                    page.remove_listener("response", handler)
        finally:
            ctx.close()
    return out

"""원문 가져오기: 최종 발행 카드의 대표 글만 본문·이미지·베스트 댓글을 읽어 옵니다.

- 화면에 올라가는 글(하루 약 30개)에만 적용합니다. 온도계용 수백 건은 열지 않습니다.
- 이미지는 복사해 저장하지 않고 원래 주소로 보여 줍니다.
- 댓글은 내용과 공감 수만 남기고 닉네임은 남기지 않습니다.
- 사이트마다 정확한 위치(선택자)는 sources.yaml의 detail 항목으로 지정합니다.
  지정이 없으면 일반 규칙(본문처럼 보이는 가장 큰 글 덩어리)으로 추정합니다.
"""

from __future__ import annotations

from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from trendbot.collectors.http import Blocked, polite_get
from trendbot.collectors.numbers import parse_count

MAX_BODY = 4000
MAX_IMAGES = 8
MAX_COMMENTS = 5
LOGIN_HINTS = ("로그인이 필요", "로그인 후", "회원만", "멤버만", "권한이 없")


def _text(el: Tag) -> str:
    for br in el.find_all("br"):
        br.replace_with("\n")
    for p in el.find_all(["p", "div"]):
        p.insert_after("\n")
    lines = [ln.strip() for ln in el.get_text().splitlines()]
    out, blank = [], 0
    for ln in lines:
        if ln:
            out.append(ln)
            blank = 0
        elif blank == 0 and out:
            out.append("")
            blank = 1
    return "\n".join(out).strip()


def _guess_body(soup: BeautifulSoup) -> Tag | None:
    for bad in soup(["script", "style", "nav", "header", "footer", "aside", "form", "noscript"]):
        bad.decompose()
    best, best_len = None, 0
    for el in soup.find_all(["article", "div", "section", "td"]):
        txt = el.get_text(" ", strip=True)
        links = sum(len(a.get_text(strip=True)) for a in el.find_all("a"))
        score = len(txt) - 2 * links
        if 30 < len(txt) < 20000 and score > best_len and len(el.find_all(["div", "article"])) < 40:
            best, best_len = el, score
    return best


def _meta(soup: BeautifulSoup, prop: str) -> str | None:
    m = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
    return (m.get("content") or "").strip() if m else None


def parse_original(html: str, url: str, detail: dict | None = None) -> dict:
    detail = detail or {}
    soup = BeautifulSoup(html, "html.parser")
    body_el = soup.select_one(detail["body"]) if detail.get("body") else None
    comments = []
    if detail.get("comment"):
        for c in soup.select(detail["comment"])[: MAX_COMMENTS * 3]:
            t = c.select_one(detail.get("comment_text", "*"))
            if not t:
                continue
            txt = t.get_text(" ", strip=True)
            if not txt:
                continue
            like = c.select_one(detail["comment_likes"]) if detail.get("comment_likes") else None
            comments.append({"text": txt[:300], "likes": parse_count(like.get_text()) if like else None})
        comments.sort(key=lambda c: -(c["likes"] or 0))
        comments = comments[:MAX_COMMENTS]
    if body_el is None:
        body_el = _guess_body(soup)

    images: list[str] = []
    if body_el is not None:
        for img in body_el.find_all("img"):
            src = img.get("data-original") or img.get("data-src") or img.get("src")
            if not src or src.startswith("data:") or any(k in src for k in ("emoticon", "icon", "blank", "spacer")):
                continue
            full = urljoin(url, src)
            if full not in images:
                images.append(full)
            if len(images) >= MAX_IMAGES:
                break
    body = _text(body_el) if body_el is not None else ""
    if not images and _meta(soup, "og:image"):
        images = [urljoin(url, _meta(soup, "og:image"))]
    if len(body) < 20:
        body = _meta(soup, "og:description") or body
    page_text = soup.get_text(" ", strip=True)[:3000]
    status = "ok" if body or images else ("login" if any(h in page_text for h in LOGIN_HINTS) else "empty")
    return {"status": status, "body": body[:MAX_BODY], "truncated": len(body) > MAX_BODY,
            "images": images, "comments": comments}


def fetch_original(url: str, source: dict | None) -> dict:
    try:
        return parse_original(polite_get(url), url, (source or {}).get("detail"))
    except Blocked as e:
        return {"status": "blocked", "body": "", "images": [], "comments": [], "note": str(e)[:120]}
    except Exception as e:
        return {"status": "error", "body": "", "images": [], "comments": [], "note": e.__class__.__name__}

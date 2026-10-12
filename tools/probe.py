"""집 PC 첫 점검: 사이트마다 접속·robots.txt·차단 여부를 확인하고, 화면 샘플을 저장합니다.

실행: python -m trendbot probe
결과: data/probe_report.md (표), tests/fixtures/<소스>.html (화면 샘플)
샘플과 보고서를 저장소에 올리면, 그 화면에 맞춰 수집기를 고칩니다.
"""

from __future__ import annotations

import json
import platform
from datetime import datetime

from trendbot.collectors import html_list
from trendbot.collectors.http import Blocked, polite_get, robots_allows
from trendbot.config import DATA_DIR, ROOT

FIX = ROOT / "tests" / "fixtures"


def _probe_html(src: dict) -> dict:
    res = {"id": src["id"], "name": src["name"], "robots": None, "fetch": "", "rows": 0, "sample": ""}
    try:
        res["robots"] = robots_allows(src["url"])
        html = polite_get(src["url"], check_robots=False)
        (FIX / f"{src['id']}.html").write_text(html, encoding="utf-8")
        res["fetch"] = f"성공 ({len(html):,}자)"
        posts = html_list.parse_list(html, src)
        res["rows"] = len(posts)
        if posts:
            p = posts[0]
            res["sample"] = f"{p.title[:30]} | 조회 {p.views} 추천 {p.likes} 댓글 {p.comments}"
    except Blocked as e:
        res["fetch"] = f"차단: {e}"
    except Exception as e:
        res["fetch"] = f"실패: {e.__class__.__name__} {str(e)[:80]}"
    return res


def _probe_naver(src: dict) -> dict:
    res = {"id": src["id"], "name": src["name"], "robots": "-", "fetch": "", "rows": 0, "sample": ""}
    try:
        from playwright.sync_api import sync_playwright

        from trendbot.collectors import naver_cafe
        payloads, urls = [], []
        with sync_playwright() as pw:
            ctx = pw.chromium.launch_persistent_context(str(naver_cafe.PROFILE_DIR), headless=False, locale="ko-KR")
            page = ctx.new_page()

            def on_resp(r):
                if "json" in (r.headers.get("content-type") or "") and "naver" in r.url:
                    urls.append(r.url)
                    try:
                        payloads.append(r.json())
                    except Exception:
                        pass

            page.on("response", on_resp)
            page.goto(src["cafe_url"], wait_until="networkidle")
            cafe_id = naver_cafe._find_cafe_id(page.content())
            page.screenshot(path=str(FIX / f"{src['id']}_home.png"))
            if cafe_id:
                page.goto(naver_cafe.POPULAR_URL.format(cafe_id=cafe_id), wait_until="networkidle")
                page.wait_for_timeout(2500)
                page.screenshot(path=str(FIX / f"{src['id']}_popular.png"), full_page=True)
            ctx.close()
        posts = naver_cafe.articles_to_posts(payloads, src, cafe_id or "?")
        (FIX / f"{src['id']}_responses.json").write_text(
            json.dumps({"cafe_id": cafe_id, "urls": urls, "payloads": payloads}, ensure_ascii=False)[:3_000_000],
            encoding="utf-8")
        res["fetch"] = f"카페번호 {cafe_id}, 응답 {len(payloads)}개"
        res["rows"] = len(posts)
        if posts:
            p = posts[0]
            res["sample"] = f"{p.title[:30]} | 조회 {p.views} 좋아요 {p.likes} 댓글 {p.comments}"
    except Exception as e:
        res["fetch"] = f"실패: {e.__class__.__name__} {str(e)[:80]} (먼저 naver-login을 했는지 확인)"
    return res


def run(cfg: dict) -> None:
    FIX.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(exist_ok=True)
    results = []
    for src in cfg["sources"]:
        print(f"점검 중: {src['name']} ...")
        r = _probe_naver(src) if src.get("kind") == "naver_cafe" else _probe_html(src)
        results.append(r)
        print(f"  → {r['fetch']} / 읽은 줄 {r['rows']}")
    for name in ("google_trends", "google_news"):
        url = cfg["signals"][name]["url"]
        try:
            text = polite_get(url, check_robots=False)
            (FIX / f"{name}.xml").write_text(text, encoding="utf-8")
            results.append({"id": name, "name": name, "robots": "-", "fetch": f"성공 ({len(text):,}자)", "rows": text.count("<item>"), "sample": ""})
        except Exception as e:
            results.append({"id": name, "name": name, "robots": "-", "fetch": f"실패: {e}", "rows": 0, "sample": ""})

    lines = [f"# 집 PC 점검 결과 ({datetime.now():%Y-%m-%d %H:%M}, {platform.system()})", "",
             "| 소스 | robots.txt | 가져오기 | 읽은 줄 | 첫 줄 예시 |", "|---|---|---|---|---|"]
    for r in results:
        rb = {True: "허용", False: "금지", None: "확인 불가"}.get(r["robots"], r["robots"])
        lines.append(f"| {r['name']} | {rb} | {r['fetch']} | {r['rows']} | {r['sample']} |")
    report = DATA_DIR / "probe_report.md"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"\n보고서 저장: {report}")
    print("다음 단계: 안내서의 '점검 결과 올리기'대로 tests/fixtures 폴더와 보고서를 저장소에 올려 주세요.")

"""만든 사이트(public/)를 브라우저로 한 장씩 열어 고장을 찾습니다.

    python tools/site_qa.py            # 휴대폰(390px)·PC(1280px) 두 크기로 점검

찾는 것: 깨진 내부 링크, 못 불러온 사진(사이트 안의 파일), 가로 스크롤(화면이 옆으로 밀림),
자바스크립트 오류. 문제가 없으면 0, 있으면 1로 끝납니다.
"""

from __future__ import annotations

import functools
import http.server
import os
import sys
import threading
from pathlib import Path
from urllib.parse import urljoin, urlparse

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public"
WIDTHS = (390, 1280)


def serve(folder: Path) -> tuple[http.server.ThreadingHTTPServer, str]:
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

    handler = functools.partial(Quiet, directory=str(folder))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}/"


def pages(folder: Path) -> list[str]:
    return sorted(str(p.relative_to(folder)).replace(os.sep, "/") for p in folder.rglob("*.html"))


def check(folder: Path = PUBLIC) -> list[str]:
    from playwright.sync_api import sync_playwright

    srv, base = serve(folder)
    problems: list[str] = []
    try:
        with sync_playwright() as pw:
            exe = os.environ.get("TRENDBOT_CHROMIUM")
            browser = pw.chromium.launch(executable_path=exe) if exe else pw.chromium.launch()
            for width in WIDTHS:
                ctx = browser.new_context(viewport={"width": width, "height": 860}, locale="ko-KR")
                # 바깥 사이트(원문 사진 등)는 점검 대상이 아님
                ctx.route(lambda u: not u.startswith(base), lambda r: r.abort())
                for rel in pages(folder):
                    page = ctx.new_page()
                    errors: list[str] = []
                    page.on("pageerror", lambda e, errors=errors: errors.append(str(e)))
                    page.goto(base + rel, wait_until="load")
                    where = f"[{width}px] {rel}"
                    for e in errors:
                        problems.append(f"{where}: 스크립트 오류 {e[:80]}")
                    over = page.evaluate("document.documentElement.scrollWidth - window.innerWidth")
                    if over > 1:
                        wide = page.evaluate("""() => [...document.querySelectorAll('body *')]
                            .filter(el => el.getBoundingClientRect().right > window.innerWidth + 1)
                            .slice(0, 3).map(el => el.tagName.toLowerCase() + (el.className ? '.' + String(el.className).split(' ')[0] : ''))""")
                        problems.append(f"{where}: 가로로 {over}px 넘침 ({', '.join(wide)})")
                    broken = page.evaluate("""() => [...document.images]
                        .filter(i => i.src.startsWith(location.origin) && i.complete && i.naturalWidth === 0)
                        .map(i => i.getAttribute('src'))""")
                    for b in broken:
                        problems.append(f"{where}: 사진 없음 {b}")
                    if width == WIDTHS[0]:  # 링크는 한 번만
                        for href in page.evaluate("[...document.querySelectorAll('a[href]')].map(a => a.getAttribute('href'))"):
                            url = urljoin(base + rel, href)
                            if not url.startswith(base) or href.startswith("#"):
                                continue
                            path = urlparse(url).path[len(urlparse(base).path):] or "index.html"
                            target = folder / path
                            if target.is_dir():
                                target = target / "index.html"
                            if not target.exists():
                                problems.append(f"{rel}: 깨진 링크 {href}")
                    page.close()
                ctx.close()
            browser.close()
    finally:
        srv.shutdown()
    return sorted(set(problems))


def main() -> int:
    if not PUBLIC.exists():
        print("public/ 이 없습니다. 먼저 python -m trendbot build-site 또는 sample 을 실행하세요.")
        return 1
    n = len(pages(PUBLIC))
    problems = check()
    print(f"페이지 {n}개 × 화면 {len(WIDTHS)}종 점검")
    for p in problems:
        print(" ✗", p)
    print("문제 없음." if not problems else f"문제 {len(problems)}건")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())

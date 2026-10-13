"""원문 이미지 저장과 본문 캡처 (GitHub 서버에서 발행 때 실행).

- 화면에 올라가는 글(발행 카드·채널 1위)의 이미지만 내려받습니다. 글당 최대 8장.
- 긴 변 1080px, webp로 줄여 data/media/<날짜>/ 에 저장하고, 사이트를 만들 때 함께 올립니다.
- 이미지를 못 받았거나, 본문에 영상·움짤·외부 삽입이 있거나, 소스 설정에 capture: true 이면
  브라우저로 글을 열어 본문 영역만 스크린샷합니다(세로로 길면 여러 장으로 나눔).
- 30일이 지나면 파일을 지웁니다(사이트에는 '원문에서 보기' 링크만 남음).
"""

from __future__ import annotations

import hashlib
import os
import io
import shutil
from datetime import date as Date
from datetime import timedelta
from urllib.parse import urlparse

import httpx

from trendbot.collectors.http import USER_AGENT
from trendbot.config import DATA_DIR

MEDIA_DIR = DATA_DIR / "media"
MAX_SIDE = 1080
MIN_BYTES = 1024          # 이보다 작으면 아이콘·자리표시로 보고 버림
MAX_IMAGES = 8
CAPTURE_WIDTH = 430       # 모바일 화면 너비로 캡처
CAPTURE_TILE = 2400       # 세로로 이 높이마다 나눠 저장
KEEP_DAYS = 30


def _name(src: str) -> str:
    return hashlib.sha1(src.encode()).hexdigest()[:16]


def to_webp(data: bytes, max_side: int = MAX_SIDE) -> bytes | None:
    from PIL import Image, ImageOps

    try:
        im = Image.open(io.BytesIO(data))
        im.seek(0)  # 움짤은 첫 장면만 (움직임은 원문 캡처·링크로)
        im = ImageOps.exif_transpose(im.convert("RGB"))
    except Exception:
        return None
    if min(im.size) < 40:
        return None
    im.thumbnail((max_side, max_side * 4))
    out = io.BytesIO()
    im.save(out, "WEBP", quality=80, method=4)
    return out.getvalue()


def download_images(srcs: list[str], page_url: str, day: str, client: httpx.Client | None = None) -> list[dict]:
    """[{"file": "media/<날짜>/<이름>.webp", "src": 원래 주소}] — 실패한 이미지는 빠짐."""
    folder = MEDIA_DIR / day
    folder.mkdir(parents=True, exist_ok=True)
    origin = f"{urlparse(page_url).scheme}://{urlparse(page_url).netloc}/"
    c = client or httpx.Client(timeout=20, follow_redirects=True)
    saved = []
    for src in srcs[:MAX_IMAGES]:
        path = folder / f"{_name(src)}.webp"
        if not path.exists():
            try:
                r = c.get(src, headers={"User-Agent": USER_AGENT, "Referer": page_url or origin,
                                        "Accept": "image/avif,image/webp,image/*,*/*;q=0.8"})
                if r.status_code != 200 or len(r.content) < MIN_BYTES or not r.headers.get("content-type", "image").startswith("image"):
                    continue
                webp = to_webp(r.content)
                if not webp:
                    continue
                path.write_bytes(webp)
            except httpx.HTTPError:
                continue
        saved.append({"file": f"media/{day}/{path.name}", "src": src})
    return saved


def split_tiles(png: bytes, day: str, key: str, tile: int = CAPTURE_TILE) -> list[str]:
    """긴 스크린샷을 세로로 나눠 webp로 저장."""
    from PIL import Image

    im = Image.open(io.BytesIO(png)).convert("RGB")
    folder = MEDIA_DIR / day
    folder.mkdir(parents=True, exist_ok=True)
    files = []
    for i, top in enumerate(range(0, im.height, tile)):
        part = im.crop((0, top, im.width, min(im.height, top + tile)))
        name = f"cap-{key}-{i}.webp"
        part.save(folder / name, "WEBP", quality=78, method=4)
        files.append(f"media/{day}/{name}")
        if i >= 5:  # 최대 6장(약 14,000px)
            break
    return files


class CaptureFailed(Exception):
    pass


def _shoot(page, el) -> bytes:
    """요소 스크린샷. 글꼴 대기로 멈추면 브라우저에 직접 영역 캡처를 요청함."""
    try:
        return el.screenshot(type="png", timeout=10000)
    except Exception:
        import base64
        box = el.bounding_box()
        scroll = page.evaluate("[window.scrollX, window.scrollY]")
        cdp = page.context.new_cdp_session(page)
        res = cdp.send("Page.captureScreenshot", {
            "format": "png", "captureBeyondViewport": True,
            "clip": {"x": box["x"] + scroll[0], "y": box["y"] + scroll[1], "width": box["width"],
                     "height": min(box["height"], 16000), "scale": 1},
        })
        return base64.b64decode(res["data"])


def capture_body(url: str, selector: str | None, day: str) -> list[str]:
    """브라우저로 글을 열어 본문 영역만 캡처. 본문 영역을 못 찾으면 실패로 처리함
    (페이지 전체를 찍으면 메뉴·닉네임이 섞이기 때문)."""
    from playwright.sync_api import sync_playwright

    if not selector:
        raise CaptureFailed("본문 위치(detail.body)가 설정되지 않음")
    png = None
    broken = False
    with sync_playwright() as pw:
        exe = os.environ.get("TRENDBOT_CHROMIUM")  # 보통은 비워 둠 (playwright install 로 설치된 것 사용)
        browser = pw.chromium.launch(executable_path=exe) if exe else pw.chromium.launch()
        for width in (CAPTURE_WIDTH, 900):  # 모바일 폭에서 본문 구조가 다르면 데스크톱 폭으로 재시도
            opts = dict(locale="ko-KR", viewport={"width": width, "height": 900}, device_scale_factor=2)
            ctx = browser.new_context(user_agent=USER_AGENT, **opts)
            try:
                page = ctx.new_page()
                # 웹폰트가 늦게 오면 캡처가 멈추므로 받지 않음(기본 글꼴로 표시)
                page.route("**/*.{woff,woff2,ttf,otf,eot}", lambda r: r.abort())
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                try:  # 광고·추적 스크립트 때문에 '조용해짐'을 끝까지 기다리지 않음
                    page.wait_for_load_state("networkidle", timeout=8000)
                except Exception:
                    pass
                # 지연 로딩 이미지가 뜨도록 끝까지 천천히 내림
                page.evaluate("""async () => { for (let y = 0; y < document.body.scrollHeight; y += 600) {
                    window.scrollTo(0, y); await new Promise(r => setTimeout(r, 150)); } window.scrollTo(0, 0); }""")
                page.wait_for_timeout(800)
                el = page.query_selector(selector)
                if el and (el.bounding_box() or {}).get("height", 0) > 20:
                    # 본문 사진이 하나도 안 떴으면 깨진 아이콘만 찍히므로 캡처하지 않음
                    shown, total = el.evaluate("""e => { const im = [...e.querySelectorAll('img')].filter(i => i.complete);
                        return [im.filter(i => i.naturalWidth > 0).length, im.length]; }""")
                    if total and not shown:
                        broken = True
                        break
                    png = _shoot(page, el)
            finally:
                ctx.close()
            if png:
                break
        browser.close()
    if broken:
        raise CaptureFailed("본문 사진을 하나도 불러오지 못함")
    if not png:
        raise CaptureFailed(f"본문 영역을 찾지 못함: {selector}")
    return split_tiles(png, day, _name(url))


def needs_capture(original: dict, saved: list[dict], source: dict | None) -> bool:
    if (source or {}).get("capture"):
        return True
    if original.get("has_media"):
        return True
    return bool(original.get("images")) and not saved


def prune(keep_days: int = KEEP_DAYS, today: Date | None = None) -> None:
    today = today or Date.today()
    if not MEDIA_DIR.exists():
        return
    for d in MEDIA_DIR.iterdir():
        try:
            if d.is_dir() and today - Date.fromisoformat(d.name) > timedelta(days=keep_days):
                shutil.rmtree(d)
        except ValueError:
            continue

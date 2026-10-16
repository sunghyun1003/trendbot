import io

from PIL import Image

from trendbot.collectors.media import to_webp, to_webp_parts


def _png(w, h):
    b = io.BytesIO()
    Image.new("RGB", (w, h), "white").save(b, "PNG")
    return b.getvalue()


def test_ai_image_fits_limit_and_site_image_keeps_width():
    tall = _png(800, 20000)
    ai = Image.open(io.BytesIO(to_webp(tall, 1024)))
    assert max(ai.size) <= 1024                       # AI는 한 변 3000px 넘으면 거절 → 1024 안으로
    parts = [Image.open(io.BytesIO(p)).size for p in to_webp_parts(tall)]
    assert all(w == 800 for w, _ in parts) and sum(h for _, h in parts) == 20000   # 사이트용은 찌그러지지 않고 나눠 저장

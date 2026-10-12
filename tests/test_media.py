"""원문 이미지 저장·캡처 도구 확인 (네트워크 없이 로컬 서버로)."""

import io
import threading
from datetime import date
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from PIL import Image

from trendbot.collectors import media


def _png(w=300, h=200, color=(240, 80, 60)):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), color).save(buf, "PNG")
    return buf.getvalue()


@pytest.fixture
def server():
    seen = {}

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            seen["referer"] = self.headers.get("Referer")
            if self.path == "/big.png":
                body, ctype = _png(2400, 1600), "image/png"
            elif self.path == "/tiny.gif":
                body, ctype = b"GIF89a" + b"\0" * 30, "image/gif"
            else:
                self.send_response(404); self.end_headers(); return
            self.send_response(200); self.send_header("Content-Type", ctype); self.end_headers(); self.wfile.write(body)

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}", seen
    srv.shutdown()


def test_download_resizes_skips_tiny_and_sends_referer(server, tmp_path, monkeypatch):
    base, seen = server
    monkeypatch.setattr(media, "MEDIA_DIR", tmp_path)
    saved = media.download_images([f"{base}/big.png", f"{base}/tiny.gif", f"{base}/missing.png"],
                                  "https://www.ppomppu.co.kr/zboard/view.php?no=1", "2026-10-12")
    assert len(saved) == 1 and saved[0]["file"].startswith("media/2026-10-12/")
    im = Image.open(tmp_path / "2026-10-12" / saved[0]["file"].split("/")[-1])
    assert im.format == "WEBP" and max(im.size) == 1080
    assert seen["referer"] == "https://www.ppomppu.co.kr/zboard/view.php?no=1"


def test_split_tiles_and_prune(tmp_path, monkeypatch):
    monkeypatch.setattr(media, "MEDIA_DIR", tmp_path)
    files = media.split_tiles(_png(430, 5000), "2026-09-01", "k")
    assert len(files) == 3
    media.split_tiles(_png(430, 100), "2026-10-11", "k")
    media.prune(30, today=date(2026, 10, 12))
    assert not (tmp_path / "2026-09-01").exists() and (tmp_path / "2026-10-11").exists()


def test_needs_capture_rules():
    assert media.needs_capture({"has_media": True, "images": []}, [], {})
    assert media.needs_capture({"images": ["a"]}, [], {})
    assert not media.needs_capture({"images": ["a"]}, [{"file": "x"}], {})
    assert media.needs_capture({"images": []}, [], {"capture": True})

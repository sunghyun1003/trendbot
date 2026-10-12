"""집 PC 도우미: 가짜 사이트·가짜 네이버로 한 바퀴 → 보낸 묶음을 클라우드 inbox가 그대로 받는지."""

import importlib.util
import io
import json
import zipfile

import pytest

from trendbot import inbox, storage
from trendbot.collectors import media, naver_cafe
from trendbot.models import Post

ROOT = __import__("pathlib").Path(__file__).resolve().parent.parent


@pytest.fixture
def helper(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("dsbg_helper", ROOT / "tools/helper/helper.py")
    h = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(h)
    app = tmp_path / "app"
    app.mkdir()
    monkeypatch.setattr(h, "APP", app)
    monkeypatch.setattr(h, "CONF", tmp_path / "config.json")
    monkeypatch.setattr(h, "STATE", tmp_path / "state.json")
    monkeypatch.setattr(h, "LOG", tmp_path / "helper.log")
    monkeypatch.setattr(h, "ACTIVE_HOURS", range(0, 24))
    monkeypatch.setattr(media, "DATA_DIR", tmp_path)
    monkeypatch.setattr(media, "MEDIA_DIR", tmp_path / "media")
    (tmp_path / "config.json").write_text(json.dumps({"token": "t" * 48, "site": "https://x.pages.dev"}))
    return h


class FakeSite:
    def __init__(self, cmd=None):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr("marker.txt", "v1")
        self.code, self.cmd, self.sent = buf.getvalue(), cmd, []

    def __call__(self, conf):
        return self

    def get(self, what):
        class R:
            content = self.code if what == "code" else b""
            json = staticmethod(lambda: {"cmd": self.cmd})
        return R()

    def put(self, what, **kw):
        self.sent.append((what, kw))


def fake_naver(monkeypatch, login=False):
    url = "https://cafe.naver.com/dieselmania/1"

    def collect(src):
        if login:
            raise naver_cafe.LoginRequired("네이버 로그인이 풀렸습니다")
        return [Post("dieselmania", "자켓 추천", url, 1, views=900), Post("dieselmania", "신발", url + "2", 2)]

    monkeypatch.setattr(naver_cafe, "collect", collect)
    monkeypatch.setattr(naver_cafe, "fetch_originals", lambda urls: {url: {"status": "ok", "body": "본문", "images": ["https://img/1.jpg"], "comments": []}})

    def download(srcs, page_url, day, client=None):
        f = media.MEDIA_DIR / day / "abcdef0123456789.webp"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b"WEBP")
        return [{"file": f"media/{day}/{f.name}", "src": srcs[0]}]

    monkeypatch.setattr(media, "download_images", download)


def test_collects_uploads_and_inbox_accepts(helper, monkeypatch, tmp_path):
    site = FakeSite()
    monkeypatch.setattr(helper, "Site", site)
    fake_naver(monkeypatch)
    assert helper.run() == 0
    kinds = [w for w, _ in site.sent]
    assert kinds == ["media", "batch", "status"]
    assert (helper.APP / "marker.txt").read_text() == "v1"  # 새 코드 풀어 둠
    status = site.sent[-1][1]["json"]
    assert status["naver"] == "ok" and status["last_collect"]

    batch = site.sent[1][1]["json"]
    db = storage.connect(tmp_path / "cloud.db")
    assert inbox.save_batch(db, json.loads(json.dumps(batch))) == 2
    assert inbox.lookup(["https://cafe.naver.com/dieselmania/1"], db)["https://cafe.naver.com/dieselmania/1"]["saved"]
    assert inbox.MEDIA_NAME.match(site.sent[0][1]["params"]["name"])

    site.sent.clear()  # 10시간 안에는 다시 수집하지 않고 상태만 알림
    assert helper.run() == 0
    assert [w for w, _ in site.sent] == ["status"]


def test_dashboard_button_forces_collect_and_login_is_reported(helper, monkeypatch):
    helper.save_state(last_collect="2999-01-01T00:00")
    site = FakeSite(cmd="collect")
    monkeypatch.setattr(helper, "Site", site)
    fake_naver(monkeypatch, login=True)
    assert helper.run() == 0
    batch = next(kw["json"] for w, kw in site.sent if w == "batch")
    assert batch["ok"] is False and "로그인" in batch["message"]
    assert site.sent[-1][1]["json"]["naver"] == "login"

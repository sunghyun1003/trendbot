import json

from tests.fake_cf import FakeCF, client
from trendbot import inbox, storage
from trendbot.collectors import media


def test_pull_imports_batch_media_and_originals(tmp_path, monkeypatch):
    monkeypatch.setattr(inbox, "DATA_DIR", tmp_path)
    fake = FakeCF()
    cf = client(fake, monkeypatch)
    cf.kv_namespace(create=True)
    url = "https://cafe.naver.com/dieselmania/1"
    fake.kv["agent:batch:2026-10-12T16:30:00+09:00"] = json.dumps({
        "source_id": "dieselmania", "at": "2026-10-12T16:30:00+09:00", "ok": True,
        "posts": [{"source_id": "dieselmania", "title": "자켓 추천", "url": url, "rank": 1, "views": 1000, "junk": 1}],
        "originals": {url: {"status": "ok", "body": "본문", "images": ["https://img/1.jpg"],
                            "saved": [{"file": "media/2026-10-12/abc.webp", "src": "https://img/1.jpg"}]}},
    }).encode()
    fake.kv["agent:media:2026-10-12/abc.webp"] = b"WEBP"
    fake.kv["agent:media:../evil.webp"] = b"x"  # 이상한 이름은 저장하지 않음
    fake.kv["agent:status"] = b"{}"
    db = storage.connect(tmp_path / "t.db")
    msg = inbox.pull(db, cf)
    assert "글 1건" in msg and "사진 2장" in msg
    assert (tmp_path / "media/2026-10-12/abc.webp").read_bytes() == b"WEBP"
    assert not (tmp_path / "evil.webp").exists()
    assert list(fake.kv) == ["agent:status"]
    assert inbox.lookup([url], db)[url]["body"] == "본문"
    assert db.execute("SELECT title FROM posts").fetchone()[0] == "자켓 추천"


def test_failed_batch_is_logged(tmp_path):
    db = storage.connect(tmp_path / "t.db")
    inbox.save_batch(db, {"source_id": "dieselmania", "ok": False, "message": "네이버 로그인이 풀렸습니다"})
    row = db.execute("SELECT ok, message FROM source_runs").fetchone()
    assert row[0] == 0 and "로그인" in row[1]


def test_adopt_copies_into_today(tmp_path, monkeypatch):
    monkeypatch.setattr(media, "DATA_DIR", tmp_path)
    monkeypatch.setattr(media, "MEDIA_DIR", tmp_path / "media")
    (tmp_path / "media/2026-10-12").mkdir(parents=True)
    (tmp_path / "media/2026-10-12/a.webp").write_bytes(b"x")
    out = media.adopt([{"file": "media/2026-10-12/a.webp", "src": "s"}, {"file": "media/2026-10-12/gone.webp", "src": "s"}], "2026-10-13")
    assert out == [{"file": "media/2026-10-13/a.webp", "src": "s"}]
    assert (tmp_path / "media/2026-10-13/a.webp").exists()

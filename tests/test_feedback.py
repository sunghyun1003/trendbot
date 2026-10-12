import json

from tests.fake_cf import FakeCF, client
from trendbot import feedback, storage


def test_pull_skips_without_keys(tmp_path, monkeypatch):
    monkeypatch.delenv("CLOUDFLARE_API_TOKEN", raising=False)
    assert "건너뜀" in feedback.pull(storage.connect(tmp_path / "f.db"))


def test_pull_saves_then_clears_kv(tmp_path, monkeypatch):
    fake = FakeCF()
    cf = client(fake, monkeypatch)
    cf.kv_namespace(create=True)
    fake.kv["fb:2026-10-13T00:00:01Z-a"] = json.dumps(
        {"at": "2026-10-13T00:00:01Z", "date": "2026-10-13", "card": "c1", "action": "keep", "user": "a@x"}).encode()
    fake.kv["fb:2026-10-13T00:00:02Z-b"] = json.dumps(
        {"at": "2026-10-13T00:00:02Z", "date": "2026-10-13", "card": "c2", "action": "drop", "reason": "이미 앎", "user": "a@x"}).encode()
    fake.kv["agent:status"] = b"{}"  # 다른 접두어는 건드리지 않음
    db = storage.connect(tmp_path / "f.db")
    assert feedback.pull(db, cf) == "피드백 2건 새로 저장"
    assert list(fake.kv) == ["agent:status"]
    assert feedback.pull(db, cf) == "피드백 0건 새로 저장"
    s = feedback.summary(db, days=100000)
    assert s["votes"] == 2 and s["keep_rate"] == 0.5 and s["already_known_rate"] == 0.5

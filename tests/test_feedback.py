import httpx

from trendbot import feedback, storage


def test_pull_skips_without_keys(tmp_path, monkeypatch):
    for k in feedback.NEEDED:
        monkeypatch.delenv(k, raising=False)
    assert "건너뜀" in feedback.pull(storage.connect(tmp_path / "f.db"))


def test_pull_saves_and_dedupes(tmp_path, monkeypatch):
    for k, v in {"SITE_URL": "https://x.pages.dev", "CF_ACCESS_CLIENT_ID": "id", "CF_ACCESS_CLIENT_SECRET": "sec",
                 "EXPORT_TOKEN": "tok"}.items():
        monkeypatch.setenv(k, v)
    seen = {}

    def handler(req: httpx.Request):
        seen["auth"] = (req.headers.get("CF-Access-Client-Id"), req.url.params.get("token"))
        return httpx.Response(200, json=[
            {"at": "2026-10-13T00:00:01Z", "date": "2026-10-13", "card": "c1", "action": "keep", "user": "a@x"},
            {"at": "2026-10-13T00:00:02Z", "date": "2026-10-13", "card": "c2", "action": "drop", "reason": "이미 앎", "user": "a@x"},
        ])

    client = httpx.Client(transport=httpx.MockTransport(handler))
    db = storage.connect(tmp_path / "f.db")
    assert feedback.pull(db, client) == "피드백 2건 새로 저장"
    assert feedback.pull(db, client) == "피드백 0건 새로 저장"
    assert seen["auth"] == ("id", "tok")
    s = feedback.summary(db, days=100000)
    assert s["votes"] == 2 and s["keep_rate"] == 0.5 and s["already_known_rate"] == 0.5


def test_pull_reports_forbidden(tmp_path, monkeypatch):
    for k in feedback.NEEDED:
        monkeypatch.setenv(k, "v" if k != "SITE_URL" else "https://x.pages.dev")
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(403)))
    assert "403" in feedback.pull(storage.connect(tmp_path / "f.db"), client)

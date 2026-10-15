import sqlite3

from trendbot import mailer


def _edition():
    card = lambda i, g: {"id": f"c{i}", "grade": g, "headline": f"헤드라인{i} <b>", "why": f"이유{i}",
                         "life": {"label": "2일째 · 확산 중 ↑"}, "terms": [{"term": "킹받네", "meaning": "열받는다", "sure": False}] if i == 1 else []}
    return {"date": "2026-10-15", "cards": [card(1, "A"), card(2, "B"), card(3, "B"), card(4, "M")]}


class FakeSMTP:
    sent = []
    def __init__(self, host, port, timeout): self.host = host
    def __enter__(self): return self
    def __exit__(self, *a): pass
    def login(self, u, p): self.user = u
    def sendmail(self, frm, to, msg): FakeSMTP.sent.append((frm, to, msg))


def test_compose_has_top3_rest_terms_and_links():
    subject, text, html = mailer.compose(_edition(), "https://dsbg.pages.dev")
    assert subject == "[ㄷㅅㅂㄱ] 10월 15일(목) 오늘의 피드 4건"
    assert "1. [전국 확산] 헤드라인1" in text and "- 헤드라인4" in text
    assert "킹받네: 열받는다 (추정)" in text
    assert "https://dsbg.pages.dev/d/2026-10-15.html#c-c1" in html
    assert "<b>" not in html.split("헤드라인1")[1][:10]  # 제목 속 꺾쇠는 글자로 처리


def test_send_once_per_day(monkeypatch, tmp_path):
    monkeypatch.setenv("GMAIL_ADDRESS", "me@gmail.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD", "abcd efgh ijkl mnop")
    to = tmp_path / "to.txt"
    to.write_text("# 주석\na@x.com\nb@y.com\n", encoding="utf-8")
    monkeypatch.setattr(mailer, "MAIL_TO", to)
    db = sqlite3.connect(":memory:")
    FakeSMTP.sent.clear()
    assert mailer.send(_edition(), "https://dsbg.pages.dev", db, FakeSMTP) == "아침 메일: 2명에게 보냄"
    assert FakeSMTP.sent[0][1] == ["a@x.com", "b@y.com"]
    assert mailer.send(_edition(), "https://dsbg.pages.dev", db, FakeSMTP) == "아침 메일: 오늘 이미 보냄"
    assert len(FakeSMTP.sent) == 1


def test_send_skips_without_settings(monkeypatch):
    monkeypatch.delenv("GMAIL_ADDRESS", raising=False)
    assert "설정 없음" in mailer.send(_edition(), "https://x", sqlite3.connect(":memory:"))

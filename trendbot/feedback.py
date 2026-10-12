"""팀원이 사이트에서 누른 유지/제외/놓친 것 기록을 집 PC로 가져옵니다.

사이트는 Cloudflare Access로 잠겨 있으므로, 서비스 토큰(CF_ACCESS_CLIENT_ID/SECRET)을 출입증으로 씁니다.
키가 없으면 조용히 건너뜁니다(발행에는 영향 없음).
"""

from __future__ import annotations

import os
import sqlite3

import httpx

SCHEMA = """
CREATE TABLE IF NOT EXISTS feedback (
  at TEXT NOT NULL, date TEXT, card TEXT, action TEXT NOT NULL,
  reason TEXT, text TEXT, user TEXT,
  UNIQUE(at, user, card, action)
);
"""
NEEDED = ("SITE_URL", "CF_ACCESS_CLIENT_ID", "CF_ACCESS_CLIENT_SECRET", "EXPORT_TOKEN")


def configured() -> bool:
    return all(os.environ.get(k) for k in NEEDED)


def fetch(client: httpx.Client | None = None, since: str = "") -> list[dict]:
    url = os.environ["SITE_URL"].rstrip("/") + "/api/feedback"
    c = client or httpx.Client(timeout=30)
    r = c.get(url, params={"token": os.environ["EXPORT_TOKEN"], "since": since},
              headers={"CF-Access-Client-Id": os.environ["CF_ACCESS_CLIENT_ID"],
                       "CF-Access-Client-Secret": os.environ["CF_ACCESS_CLIENT_SECRET"]})
    r.raise_for_status()
    return r.json()


def save(db: sqlite3.Connection, rows: list[dict]) -> int:
    db.executescript(SCHEMA)
    before = db.total_changes
    db.executemany(
        "INSERT OR IGNORE INTO feedback VALUES(?,?,?,?,?,?,?)",
        [(r.get("at"), r.get("date"), r.get("card"), r.get("action"), r.get("reason"), r.get("text"), r.get("user"))
         for r in rows if r.get("at") and r.get("action")],
    )
    db.commit()
    return db.total_changes - before


def pull(db: sqlite3.Connection, client: httpx.Client | None = None) -> str:
    """가져와 저장하고, 결과를 한국어 한 줄로 돌려줌."""
    if not configured():
        return "피드백 가져오기: 키가 없어 건너뜀 (docs/keys-guide.md 4번)"
    db.executescript(SCHEMA)
    last = db.execute("SELECT MAX(at) FROM feedback").fetchone()[0] or ""
    try:
        rows = fetch(client, since=last[:10])
    except httpx.HTTPStatusError as e:
        code = e.response.status_code
        hint = {401: "사이트 쪽 Access 설정(AUD) 확인", 403: "EXPORT_TOKEN 또는 서비스 토큰 정책 확인"}.get(code, "")
        return f"피드백 가져오기 실패: {code} {hint}".strip()
    except httpx.HTTPError as e:
        return f"피드백 가져오기 실패: {e.__class__.__name__}"
    return f"피드백 {save(db, rows)}건 새로 저장"


def summary(db: sqlite3.Connection, days: int = 14) -> dict:
    """최근 유지율·이미 앎 비율 (기준 조정용)."""
    db.executescript(SCHEMA)
    rows = db.execute(
        "SELECT action, reason FROM feedback WHERE date >= date('now', ?)", (f"-{days} days",)
    ).fetchall()
    keep = sum(1 for a, _ in rows if a == "keep")
    drop = sum(1 for a, _ in rows if a == "drop")
    known = sum(1 for a, r in rows if a == "drop" and r == "이미 앎")
    total = keep + drop
    return {"votes": total, "keep_rate": round(keep / total, 2) if total else None,
            "already_known_rate": round(known / total, 2) if total else None,
            "missed": sum(1 for a, _ in rows if a == "missed")}

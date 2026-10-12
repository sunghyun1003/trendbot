"""팀원이 사이트에서 누른 유지/제외/놓친 것 기록을 가져옵니다.

사이트 버튼 → Cloudflare KV(fb: 접두어)에 저장 → 발행 때 Cloudflare API로 읽어 DB에 넣고 KV에서는 지움.
Cloudflare 키가 없으면 조용히 건너뜁니다(발행에는 영향 없음).
"""

from __future__ import annotations

import json
import sqlite3

from trendbot import cloudflare

SCHEMA = """
CREATE TABLE IF NOT EXISTS feedback (
  at TEXT NOT NULL, date TEXT, card TEXT, action TEXT NOT NULL,
  reason TEXT, text TEXT, user TEXT,
  UNIQUE(at, user, card, action)
);
"""
PREFIX = "fb:"


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


def pull(db: sqlite3.Connection, client: "cloudflare.Client | None" = None) -> str:
    """가져와 저장하고, 결과를 한국어 한 줄로 돌려줌."""
    if not client and not cloudflare.configured():
        return "피드백 가져오기: Cloudflare 키가 없어 건너뜀"
    try:
        cf = client or cloudflare.Client()
        keys = cf.kv_keys(PREFIX)
        rows = [json.loads(cf.kv_get(k)) for k in keys]
        n = save(db, rows)
        cf.kv_delete(keys)  # DB에 옮겼으니 지움 (다음엔 새 것만)
    except (cloudflare.CloudflareError, ValueError) as e:
        return f"피드백 가져오기 실패: {e}"[:200]
    return f"피드백 {n}건 새로 저장"


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

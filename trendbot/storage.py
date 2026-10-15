"""SQLite 저장소 (GitHub 서버, data 브랜치에 보관). 제목·링크·수치만 저장합니다 (본문·닉네임 없음)."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from trendbot.config import DATA_DIR
from trendbot.models import Post, Signal, now_iso

DB_PATH = DATA_DIR / "trendbot.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
  id INTEGER PRIMARY KEY,
  source_id TEXT NOT NULL,
  url TEXT NOT NULL,
  title TEXT NOT NULL,
  first_seen TEXT NOT NULL,
  posted_at TEXT,
  UNIQUE(source_id, url)
);
CREATE TABLE IF NOT EXISTS snapshots (
  post_id INTEGER NOT NULL REFERENCES posts(id),
  taken_at TEXT NOT NULL,
  rank INTEGER, views INTEGER, likes INTEGER, comments INTEGER
);
CREATE INDEX IF NOT EXISTS snap_taken ON snapshots(taken_at);
CREATE TABLE IF NOT EXISTS signals (
  kind TEXT NOT NULL, title TEXT NOT NULL, url TEXT, value INTEGER,
  extra TEXT, taken_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS sig_taken ON signals(taken_at);
CREATE TABLE IF NOT EXISTS source_runs (
  source_id TEXT NOT NULL, taken_at TEXT NOT NULL, ok INTEGER NOT NULL,
  rows INTEGER, message TEXT
);
CREATE TABLE IF NOT EXISTS editions (
  date TEXT PRIMARY KEY, body TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS published_stories (
  story_key TEXT NOT NULL, date TEXT NOT NULL, tokens TEXT NOT NULL,
  pods TEXT NOT NULL, post_urls TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS champions_shown (
  source_id TEXT NOT NULL, url TEXT NOT NULL, date TEXT NOT NULL,
  PRIMARY KEY(source_id, url)
);
CREATE TABLE IF NOT EXISTS champion_history (
  source_id TEXT NOT NULL, date TEXT NOT NULL, score REAL NOT NULL,
  PRIMARY KEY(source_id, date)
);
"""


def connect(path: Path = DB_PATH) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)
    return db


def save_posts(db: sqlite3.Connection, posts: list[Post], taken_at: str | None = None) -> None:
    taken_at = taken_at or now_iso()
    for p in posts:
        db.execute(
            "INSERT INTO posts(source_id,url,title,first_seen,posted_at) VALUES(?,?,?,?,?) "
            "ON CONFLICT(source_id,url) DO UPDATE SET title=excluded.title",
            (p.source_id, p.url, p.title, taken_at, p.posted_at),
        )
        pid = db.execute("SELECT id FROM posts WHERE source_id=? AND url=?", (p.source_id, p.url)).fetchone()[0]
        db.execute(
            "INSERT INTO snapshots(post_id,taken_at,rank,views,likes,comments) VALUES(?,?,?,?,?,?)",
            (pid, taken_at, p.rank, p.views, p.likes, p.comments),
        )
    db.commit()


def save_signals(db: sqlite3.Connection, signals: list[Signal], taken_at: str | None = None) -> None:
    taken_at = taken_at or now_iso()
    db.executemany(
        "INSERT INTO signals(kind,title,url,value,extra,taken_at) VALUES(?,?,?,?,?,?)",
        [(s.kind, s.title, s.url, s.value, json.dumps(s.extra, ensure_ascii=False), taken_at) for s in signals],
    )
    db.commit()


def log_run(db: sqlite3.Connection, source_id: str, ok: bool, rows: int, message: str = "") -> None:
    db.execute("INSERT INTO source_runs VALUES(?,?,?,?,?)", (source_id, now_iso(), int(ok), rows, message))
    db.commit()


def window_posts(db: sqlite3.Connection, since: str) -> list[dict]:
    """기간 안에 본 글마다 가장 좋은 순위와 가장 큰 수치를 돌려줌."""
    rows = db.execute(
        """
        SELECT p.source_id, p.url, p.title, p.first_seen,
               MIN(s.rank) AS best_rank, MAX(s.views) AS views,
               MAX(s.likes) AS likes, MAX(s.comments) AS comments,
               COUNT(*) AS sightings
        FROM posts p JOIN snapshots s ON s.post_id = p.id
        WHERE s.taken_at >= ?
        GROUP BY p.id
        """,
        (since,),
    ).fetchall()
    return [dict(r) for r in rows]


def window_signals(db: sqlite3.Connection, since: str) -> list[dict]:
    rows = db.execute(
        "SELECT kind,title,url,MAX(value) AS value,extra,MIN(taken_at) AS first_at FROM signals "
        "WHERE taken_at >= ? GROUP BY kind,title",
        (since,),
    ).fetchall()
    return [{**dict(r), "extra": json.loads(r["extra"] or "{}")} for r in rows]


def source_health(db: sqlite3.Connection, since: str) -> dict[str, dict]:
    rows = db.execute(
        "SELECT source_id, ok, rows, message, taken_at FROM source_runs WHERE taken_at >= ? ORDER BY taken_at",
        (since,),
    ).fetchall()
    health: dict[str, dict] = {}
    for r in rows:
        prev = health.get(r["source_id"], {})
        last_ok = r["taken_at"] if r["ok"] else prev.get("last_ok")
        health[r["source_id"]] = {"ok": bool(r["ok"]), "rows": r["rows"], "message": r["message"], "at": r["taken_at"],
                                  "last_ok": last_ok, "last_rows": r["rows"] if r["ok"] else prev.get("last_rows")}
    return health


def recent_published(db: sqlite3.Connection, before_date: str, days: int = 7) -> list[dict]:
    start = (datetime.fromisoformat(before_date) - timedelta(days=days)).date().isoformat()
    rows = db.execute(
        "SELECT * FROM published_stories WHERE date >= ? AND date < ?", (start, before_date)
    ).fetchall()
    return [
        {**dict(r), "tokens": set(json.loads(r["tokens"])), "pods": set(json.loads(r["pods"])),
         "post_urls": set(json.loads(r["post_urls"]))}
        for r in rows
    ]


def shown_champion_urls(db: sqlite3.Connection, before_date: str) -> set[tuple[str, str]]:
    rows = db.execute("SELECT source_id,url FROM champions_shown WHERE date < ?", (before_date,)).fetchall()
    return {(r[0], r[1]) for r in rows}


def champion_scores(db: sqlite3.Connection, source_id: str, before_date: str, days: int = 30) -> list[float]:
    start = (datetime.fromisoformat(before_date) - timedelta(days=days)).date().isoformat()
    rows = db.execute(
        "SELECT score FROM champion_history WHERE source_id=? AND date>=? AND date<?", (source_id, start, before_date)
    ).fetchall()
    return [r[0] for r in rows]


def save_edition(db: sqlite3.Connection, edition: dict) -> None:
    date = edition["date"]
    db.execute("INSERT OR REPLACE INTO editions VALUES(?,?,?)", (date, json.dumps(edition, ensure_ascii=False), now_iso()))
    db.execute("DELETE FROM published_stories WHERE date=?", (date,))
    for c in edition["cards"]:
        db.execute(
            "INSERT INTO published_stories VALUES(?,?,?,?,?)",
            (c["id"], date, json.dumps(sorted(c["tokens"]), ensure_ascii=False), json.dumps(sorted(c["pods"])),
             json.dumps([p["url"] for p in c["posts"]])),
        )
    for ch in edition["champions"]:
        if ch.get("post"):
            db.execute("INSERT OR IGNORE INTO champions_shown VALUES(?,?,?)", (ch["source_id"], ch["post"]["url"], date))
            db.execute("INSERT OR REPLACE INTO champion_history VALUES(?,?,?)", (ch["source_id"], date, ch["score"]))
    db.commit()


def load_editions(db: sqlite3.Connection) -> list[dict]:
    return [json.loads(r[0]) for r in db.execute("SELECT body FROM editions ORDER BY date DESC").fetchall()]


def prune(db: sqlite3.Connection, keep_days: int = 60) -> None:
    """오래된 온도계 데이터 정리 (발행된 판은 유지)."""
    cutoff = (datetime.now() - timedelta(days=keep_days)).isoformat()
    db.execute("DELETE FROM snapshots WHERE taken_at < ?", (cutoff,))
    db.execute("DELETE FROM signals WHERE taken_at < ?", (cutoff,))
    db.execute("DELETE FROM posts WHERE id NOT IN (SELECT DISTINCT post_id FROM snapshots)")
    db.execute("DELETE FROM source_runs WHERE taken_at < ?", (cutoff,))
    db.commit()

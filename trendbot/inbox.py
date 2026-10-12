"""집 PC 도우미가 보낸 디젤매니아(네이버 카페) 수집 결과를 받아 DB에 넣습니다 (GitHub 서버에서 실행).

도우미 → 사이트(/api/agent) → Cloudflare KV
- agent:batch:<시각>   목록 + 상위 글 원문 (JSON)
- agent:media:<날짜>/<이름>.webp   원문 사진 (도우미가 줄여서 보냄)
받은 뒤에는 KV에서 지웁니다. 원문은 prefetched 표에 두었다가 발행 때 씁니다.
"""

from __future__ import annotations

import json
import re
import sqlite3

from trendbot import cloudflare, storage
from trendbot.config import DATA_DIR
from trendbot.models import Post

SCHEMA = "CREATE TABLE IF NOT EXISTS prefetched (url TEXT PRIMARY KEY, original TEXT NOT NULL, at TEXT NOT NULL);"
MEDIA_NAME = re.compile(r"^\d{4}-\d{2}-\d{2}/[\w-]+\.webp$")


def save_batch(db: sqlite3.Connection, b: dict) -> int:
    db.executescript(SCHEMA)
    src = b.get("source_id", "dieselmania")
    if not b.get("ok"):
        storage.log_run(db, src, False, 0, (b.get("message") or "집 PC 도우미 수집 실패")[:200])
        return 0
    posts = [Post(**{k: v for k, v in p.items() if k in Post.__dataclass_fields__}) for p in b.get("posts", [])]
    storage.save_posts(db, posts, taken_at=b.get("at"))
    storage.log_run(db, src, True, len(posts), "집 PC 도우미")
    for url, o in (b.get("originals") or {}).items():
        db.execute("INSERT OR REPLACE INTO prefetched VALUES(?,?,?)", (url, json.dumps(o, ensure_ascii=False), b.get("at") or ""))
    db.commit()
    return len(posts)


def lookup(urls: list[str], db: sqlite3.Connection | None = None) -> dict[str, dict]:
    db = db or storage.connect()
    db.executescript(SCHEMA)
    out = {}
    for u in urls:
        row = db.execute("SELECT original FROM prefetched WHERE url=?", (u,)).fetchone()
        if row:
            out[u] = json.loads(row[0])
    return out


def pull(db: sqlite3.Connection, client: "cloudflare.Client | None" = None) -> str:
    if not client and not cloudflare.configured():
        return "집 PC 도우미 결과: Cloudflare 키가 없어 건너뜀"
    try:
        cf = client or cloudflare.Client()
        media_keys = cf.kv_keys("agent:media:")
        for k in media_keys:
            name = k.removeprefix("agent:media:")
            if MEDIA_NAME.match(name):
                path = DATA_DIR / "media" / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(cf.kv_get(k))
        batch_keys = cf.kv_keys("agent:batch:")
        rows = sum(save_batch(db, json.loads(cf.kv_get(k))) for k in batch_keys)
        cf.kv_delete(media_keys + batch_keys)
    except (cloudflare.CloudflareError, ValueError) as e:
        return f"집 PC 도우미 결과 받기 실패: {e}"[:200]
    return f"집 PC 도우미 결과: 묶음 {len(batch_keys)}개, 글 {rows}건, 사진 {len(media_keys)}장"

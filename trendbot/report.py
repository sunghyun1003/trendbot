"""`python -m trendbot report` — 수집이 잘 됐는지 숫자로 보여 주는 품질 리포트.

사이트마다: 마지막 수집 성공 여부, 읽은 글 수, 조회·추천·댓글 수치가 채워진 비율, 1위 글 예시.
원문(화면에 올라간 글)마다: 본문·사진·댓글을 가져왔는지, 캡처를 했는지.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta

from trendbot import storage
from trendbot.config import DATA_DIR


def _pct(n: int, d: int) -> str:
    return f"{round(100 * n / d)}%" if d else "-"


def source_rows(db: sqlite3.Connection, cfg: dict, hours: int = 26) -> list[dict]:
    since = (datetime.now().astimezone() - timedelta(hours=hours)).isoformat()
    posts = storage.window_posts(db, since)
    health = storage.source_health(db, since)
    out = []
    for src in cfg["sources"]:
        mine = sorted([p for p in posts if p["source_id"] == src["id"]], key=lambda p: p["best_rank"])
        h = health.get(src["id"], {})
        if not src.get("enabled", True):
            state = "꺼짐"
        elif not h:
            state = "기록 없음"
        else:
            state = "정상" if h["ok"] else f"실패: {h['message'][:40]}"
        n = len(mine)
        out.append({
            "name": src["name"], "state": state, "posts": n,
            "views": _pct(sum(1 for p in mine if p["views"]), n),
            "likes": _pct(sum(1 for p in mine if p["likes"]), n) if "likes" in src.get("fields", {}) else "해당 없음",
            "comments": _pct(sum(1 for p in mine if p["comments"]), n),
            "top": mine[0]["title"][:34] if mine else "",
        })
    return out


def original_rows(edition: dict) -> list[dict]:
    posts = [(c.get("headline", ""), p) for c in edition.get("cards", []) for p in c["posts"][:2]]
    posts += [(ch["name"], ch["post"]) for ch in edition.get("champions", []) if ch.get("post") and not ch.get("in_card")]
    out = []
    for label, p in posts:
        o = p.get("original")
        if not o:
            continue
        out.append({
            "where": p.get("source_name") or label, "title": p["title"][:30], "status": o.get("status"),
            "body": len(o.get("body", "")), "images": len(o.get("images", [])), "saved": len(o.get("saved", [])),
            "capture": len(o.get("capture", [])), "comments": len(o.get("comments", [])),
        })
    return out


def render(src_rows: list[dict], orig_rows: list[dict], edition: dict | None) -> str:
    lines = [f"# 수집 품질 리포트 ({datetime.now():%Y-%m-%d %H:%M})", "", "## 1. 사이트별 목록 수집 (최근 26시간)", "",
             "| 사이트 | 상태 | 읽은 글 | 조회수 있음 | 추천 있음 | 댓글수 있음 | 1위 글 |", "|---|---|---|---|---|---|---|"]
    for r in src_rows:
        lines.append(f"| {r['name']} | {r['state']} | {r['posts']} | {r['views']} | {r['likes']} | {r['comments']} | {r['top']} |")
    ok = sum(1 for r in src_rows if r["state"] == "정상")
    on = sum(1 for r in src_rows if r["state"] != "꺼짐")
    lines += ["", f"켜진 사이트 {on}곳 중 {ok}곳 정상.", ""]
    if edition is not None:
        lines += ["## 2. 오늘의 판", "",
                  f"- 필수 카드 {len(edition.get('cards', []))}장, 채널 1위 {sum(1 for c in edition.get('champions', []) if c.get('post'))}줄",
                  f"- AI 편집: {'사용' if (edition.get('ai') or {}).get('used') else '안 함'} {(edition.get('ai') or {}).get('note') or ''}", ""]
    b = (edition or {}).get("benchmark")
    if b:
        lines += [f"## 외부 기준 대조 ({b['source']})", "",
                  f"- 상위 {b['total']}개 중 수집됨 {b['collected']}, 판에 오름 {b['in_edition']}", ""]
        lines += [f"  - [{m['site']}] {m['title']} ({b.get('metric', '조회')} {m['views']}) — {'수집됨, 판에서 빠짐' if m['collected'] else '수집 안 됨'}"
                  for m in b["missed"]] + [""]
    lines += ["## 3. 원문 가져오기 (화면에 올라간 글만)", "",
              "| 위치 | 제목 | 결과 | 본문 글자 | 사진 주소 | 사진 저장 | 캡처 | 베스트 댓글 |", "|---|---|---|---|---|---|---|---|"]
    for r in orig_rows:
        lines.append(f"| {r['where']} | {r['title']} | {r['status']} | {r['body']} | {r['images']} | {r['saved']} | {r['capture']} | {r['comments']} |")
    if orig_rows:
        ok_o = sum(1 for r in orig_rows if r["status"] == "ok")
        lines += ["", f"원문 {len(orig_rows)}개 중 {ok_o}개 성공, 사진 있는 글 {sum(1 for r in orig_rows if r['images'])}개, "
                      f"댓글 있는 글 {sum(1 for r in orig_rows if r['comments'])}개."]
    return "\n".join(lines) + "\n"


def run(cfg: dict) -> str:
    db = storage.connect()
    editions = storage.load_editions(db)
    edition = editions[0] if editions else None
    text = render(source_rows(db, cfg), original_rows(edition) if edition else [], edition)
    (DATA_DIR / "quality_report.md").write_text(text, encoding="utf-8")
    return text

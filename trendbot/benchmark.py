"""외부 기준 대조 (벤치마크): 이슈링크 '커뮤니티 베스트 1일' 순위와 우리 아침 판을 비교합니다.

- 이슈링크 상위 글 중, 원래 사이트가 수집을 허용하는 곳(우리가 수집 중인 곳)의 글만 비교합니다.
  (클리앙·MLB파크·이토랜드·오늘의유머·SLR·딴지는 원래 사이트가 거부·차단하므로 비교에서도 제외)
- 결과: 우리 '온도계'에 들어왔는지(수집됨), 아침 판에 올랐는지(판에 오름), 놓친 글 목록.
  수집은 됐는데 판에 없으면 판정 기준 문제, 수집조차 안 됐으면 수집 범위 문제로 읽으면 됩니다.
"""

from __future__ import annotations

import re
import sqlite3
from datetime import datetime, timedelta

from bs4 import BeautifulSoup

from trendbot import storage
from trendbot.collectors.http import polite_get
from trendbot.collectors.numbers import parse_count

URLS = ["https://www.issuelink.co.kr/community/listview/all/24/adj/_self/blank/blank/blank",
        "https://www.issuelink.co.kr/community/listview/all/24/comment/_self"]
# 이슈링크 사이트 코드 → 우리 소스 id (우리가 수집하는 곳만)
CODE_TO_SOURCES = {
    "fmkorea": ["fmkorea"], "theqoo": ["theqoo"], "ruliweb": ["ruliweb"], "ppomppu": ["ppomppu_hot", "ppomppu_deal"],
    "humoruniv": ["humoruniv"], "inven": ["inven"], "bobae": ["bobaedream"], "instiz": ["instiz"], "82cook": ["cook82"],
}
CODE_LABEL = {"fmkorea": "펨코", "theqoo": "더쿠", "ruliweb": "루리웹", "ppomppu": "뽐뿌", "humoruniv": "웃대",
              "inven": "인벤", "bobae": "보배", "instiz": "인티", "82cook": "82쿡"}
TOP_N = 40


def parse(html: str) -> list[dict]:
    out = []
    for tr in BeautifulSoup(html, "html.parser").select("tr"):
        a = tr.select_one("span.title a")
        m = re.search(r"/go/([a-z0-9_]+)/", a["href"]) if a and a.get("href") else None
        if not m:
            continue
        small = a.select_one("small")
        comments = parse_count(small.get_text()) if small else None
        if small:
            small.decompose()
        hit = tr.select_one("span.hit")
        out.append({"code": m.group(1), "title": " ".join(a.get_text().split()),
                    "views": parse_count(hit.get_text()) if hit else None, "comments": comments})
    return out


def _norm(t: str) -> str:
    t = re.sub(r"\.(jpg|jpeg|gif|png|mp4|webp|gif)\b", "", t.lower())
    return re.sub(r"[\s\W_]+", "", t)


def same(a: str, b: str) -> bool:
    """제목이 같은 글인지 (사이트마다 말줄임·확장자·괄호가 달라 느슨하게 비교)."""
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return False
    if na == nb or (min(len(na), len(nb)) >= 8 and (na in nb or nb in na)):
        return True
    grams = lambda s: {s[i:i + 2] for i in range(len(s) - 1)}
    ga, gb = grams(na), grams(nb)
    return bool(ga and gb) and len(ga & gb) / len(ga | gb) >= 0.6


def compare(ranked: list[dict], edition: dict, collected: list[dict]) -> dict:
    ours = [r for r in ranked if r["code"] in CODE_TO_SOURCES][:TOP_N]
    shown = [p for c in edition.get("cards", []) for p in c.get("posts", [])]
    shown += [ch["post"] for ch in edition.get("champions", []) if ch.get("post")]
    rows = []
    for r in ours:
        srcs = CODE_TO_SOURCES[r["code"]]
        got = any(p["source_id"] in srcs and same(r["title"], p["title"]) for p in collected)
        on = any(same(r["title"], p.get("title", "")) for p in shown)
        rows.append({**r, "site": CODE_LABEL.get(r["code"], r["code"]), "collected": got, "in_edition": on})
    n = len(rows)
    return {
        "source": "이슈링크 커뮤니티 베스트 1일", "metric": "조회", "total": n,
        "collected": sum(r["collected"] for r in rows), "in_edition": sum(r["in_edition"] for r in rows),
        "missed": [r for r in rows if not r["in_edition"]][:10],
    }


def run(db: sqlite3.Connection, edition: dict) -> dict | None:
    """실패하면 None (발행에는 영향 없음)."""
    html, used = None, None
    for url in URLS:  # 기본은 '조회 보정순', 서버가 바쁘면 '댓글순'으로
        try:
            html, used = polite_get(url), url
            break
        except Exception:
            continue
    if not html:
        return None
    ranked = parse(html)
    if not ranked:
        return None
    since = (datetime.now().astimezone() - timedelta(hours=36)).isoformat()
    out = compare(ranked, edition, storage.window_posts(db, since))
    if "/comment/" in used:  # 댓글순 화면에서는 숫자가 댓글 수
        out.update(source="이슈링크 커뮤니티 베스트 1일 (댓글순)", metric="댓글")
    return out

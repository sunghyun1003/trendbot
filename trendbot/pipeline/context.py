"""제목만 있는 글(펨코·인스티즈처럼 원문을 열 수 없는 곳) 보강.

1. 같은 이야기를 다룬 다른 사이트 글이 있으면 → 그 글의 원문(본문·이미지)을 함께 보여 줌
2. 없으면 → 관련 뉴스 기사를 찾아(이미 모은 뉴스 먼저, 없으면 구글 뉴스 검색) AI가 2줄로 요약
   AI는 기사가 정말 같은 이야기인지도 판단하고, 아니면 붙이지 않음 (엉뚱한 기사 방지)
"""

from __future__ import annotations

import os

from trendbot.pipeline import cluster as cl

MAX_ITEMS = 12          # 하루에 보강하는 글 수 (요청·비용 상한)
NEWS_PER_ITEM = 4


def _keywords(title: str) -> list[str]:
    toks = sorted(cl.tokens(title), key=len, reverse=True)
    return [t for t in toks if len(t) >= 2][:4]


def same_story_alt(post: dict, stories: list[cl.Story], content_sources: set[str]) -> dict | None:
    """이 글과 같은 이야기 묶음에서, 원문을 열 수 있는 사이트의 글 하나."""
    for s in stories:
        if any(i.url == post["url"] for i in s.posts):
            alts = [i for i in s.posts if i.source_id in content_sources and i.url != post["url"]]
            if alts:
                a = min(alts, key=lambda i: i.data.get("best_rank") or 99)
                return {"source_id": a.source_id, "title": a.title, "url": a.url,
                        "views": a.data.get("views"), "comments": a.data.get("comments")}
            return None
    return None


def local_news(title: str, signals: list[dict]) -> list[dict]:
    """이미 모아 둔 뉴스(구글 뉴스·연예 랭킹·트렌드 관련 기사) 중 제목 낱말이 2개 이상 겹치는 기사."""
    want = set(_keywords(title))
    pool = []
    for s in signals:
        if s["kind"] in ("google_news", "ent_news"):
            pool.append({"title": s["title"], "url": s.get("url") or "", "source": (s.get("extra") or {}).get("press", "")})
        for n in (s.get("extra") or {}).get("news") or []:
            pool.append({"title": n.get("title", ""), "url": n.get("url", ""), "source": n.get("source", "")})
    hits = [n for n in pool if len(want & cl.tokens(n["title"])) >= 2]
    seen, out = set(), []
    for n in hits:
        if n["title"] not in seen:
            seen.add(n["title"])
            out.append(n)
    return out[:NEWS_PER_ITEM]


def search_news(title: str, get=None) -> list[dict]:
    """네이버 검색 API(뉴스, 공식 API·무료). 키(NAVER_CLIENT_ID·SECRET)가 없으면 빈 목록.
    구글 뉴스 검색은 robots.txt가 금지해서 쓰지 않음."""
    cid, secret = os.environ.get("NAVER_CLIENT_ID"), os.environ.get("NAVER_CLIENT_SECRET")
    kw = _keywords(title)
    if not (cid and secret) or len(kw) < 2:
        return []
    import html
    import re

    import httpx
    try:
        r = (get or httpx.get)("https://openapi.naver.com/v1/search/news.json",
                               params={"query": " ".join(kw), "display": NEWS_PER_ITEM, "sort": "sim"},
                               headers={"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": secret}, timeout=10)
        r.raise_for_status()
        items = r.json().get("items", [])
    except Exception:
        return []
    clean = lambda t: html.unescape(re.sub(r"<[^>]+>", "", t or "")).strip()
    return [{"title": clean(i.get("title")), "url": i.get("originallink") or i.get("link") or "",
             "source": "", "desc": clean(i.get("description"))} for i in items][:NEWS_PER_ITEM]


def needs_context(post: dict) -> bool:
    o = post.get("original") or {}
    return not (o.get("status") == "ok" and (o.get("body") or o.get("images")))


def enrich(posts: list[dict], stories: list[cl.Story], signals: list[dict], cfg: dict, use_ai: bool = True,
           search=search_news) -> None:
    """posts(채널 1위·카드 대표 글 중 내용 없는 것)에 alt(다른 사이트 원문) 또는 news_ctx(관련 기사 요약)를 붙임."""
    from trendbot.pipeline.edition import attach_originals
    content_sources = {s["id"] for s in cfg["sources"] if s.get("original") is not False}
    todo = [p for p in posts if needs_context(p)][:MAX_ITEMS]
    ask = []
    for p in todo:
        alt = same_story_alt(p, stories, content_sources)
        if alt:
            attach_originals([alt], cfg)
            if not needs_context(alt):
                alt["source_name"] = next(s["name"] for s in cfg["sources"] if s["id"] == alt["source_id"])
                p["alt"] = alt
                continue
        news = local_news(p["title"], signals) or search(p["title"])
        if news:
            ask.append((p, news))
    results = summarize([(p["title"], news) for p, news in ask]) if use_ai and ask else {}
    for i, (p, news) in enumerate(ask):
        r = results.get(i)
        if r and r.get("related"):
            p["news_ctx"] = {"summary": r["summary"], "articles": news[:3]}
    print(f"제목만 있는 글 보강: 대상 {len(todo)} · 다른 사이트 원문 {sum(1 for p in todo if p.get('alt'))}"
          f" · 기사 후보 {len(ask)} · 관련 기사 요약 {sum(1 for p in todo if p.get('news_ctx'))}")


SCHEMA = {
    "type": "object",
    "properties": {"items": {"type": "array", "items": {
        "type": "object",
        "properties": {"i": {"type": "integer"}, "related": {"type": "boolean"}, "summary": {"type": "string"}},
        "required": ["i", "related", "summary"], "additionalProperties": False}}},
    "required": ["items"], "additionalProperties": False,
}
PROMPT = """커뮤니티 글 제목과, 제목 낱말로 찾은 뉴스 기사 제목들이 있다.
각 항목마다:
- related: 기사들이 이 글과 **같은 일**을 다루면 true, 아니면 false (낱말만 겹치고 다른 일이면 false)
- summary: related일 때만, 기사 제목에 근거해 '무슨 일인지'를 2문장 이내 60자 안팎으로. 기사에 없는 사실은 쓰지 않는다. related가 false면 빈 문자열.
"""


def summarize(items: list[tuple[str, list[dict]]]) -> dict[int, dict]:
    if not items or not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        return {}
    import json

    import anthropic

    from trendbot.pipeline.editor import MODEL
    payload = [{"i": i, "post_title": t, "news": [(n["title"] + (" — " + n["desc"][:120] if n.get("desc") else "")) for n in news]}
               for i, (t, news) in enumerate(items)]
    try:
        resp = anthropic.Anthropic(max_retries=2).messages.create(
            model=MODEL, max_tokens=4000, system=PROMPT,
            output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
            messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}])
    except anthropic.APIError as e:
        print(f"관련 기사 요약 실패: {e.__class__.__name__}")
        return {}
    if resp.stop_reason != "end_turn":
        return {}
    text = next((b.text for b in resp.content if b.type == "text"), "")
    try:
        return {x["i"]: x for x in json.loads(text).get("items", [])}
    except (ValueError, AttributeError):
        return {}

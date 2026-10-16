"""하루치 '판(edition)' 조립: 판정 → 맥락 → AI 편집 → 상한 → 채널 1위."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta

from trendbot import storage
from trendbot.collectors.original import fetch_original
from trendbot.config import sources_by_id
from trendbot.models import now_iso
from trendbot.pipeline import cluster as cl
from trendbot.pipeline import editor
from trendbot.pipeline.grade import GRADE_ORDER, Candidate, champions, select


def _fmt(n: int | None) -> str:
    if n is None:
        return "-"
    if n >= 10_000:
        return f"{n / 10_000:.1f}만".replace(".0만", "만")
    return f"{n:,}"


def _evidence_line(c: Candidate, cfg: dict) -> str:
    pods = cfg["pods"]
    parts = []
    community = sorted(c.community_pods)
    if community:
        parts.append(" · ".join(pods[p]["label"] for p in community))
    if c.traffic:
        parts.append(f"구글 트렌드 {_fmt(c.traffic)}+")
    if c.news_count:
        parts.append(f"주요 뉴스 {c.news_count}건")
    if c.yt_views:
        parts.append(f"유튜브 {_fmt(c.yt_views)}회")
    xranks = [i.data.get("extra", {}).get("rank") or 99 for i in c.story.items if i.kind == "xtrend"]
    if xranks:
        parts.append(f"X 트렌드 {min(xranks)}위" if min(xranks) < 99 else "X 트렌드")
    return " + ".join(parts)


def _age_label(c: Candidate, cfg: dict) -> str:
    pods = cfg["pods"]
    if c.gender_cross and c.age_cross:
        return "전 연령 (확산 기반 추정)"
    labels = [pods[p]["label"] for p in sorted(c.community_pods)]
    return (", ".join(labels) + " 중심 (확산 기반 추정)") if labels else "추정 불가"


def attach_originals(posts: list[dict], cfg: dict) -> None:
    """발행될 글에 원문(본문·이미지·베스트 댓글)을 붙임."""
    srcs = sources_by_id(cfg)
    for p in posts:
        src = srcs.get(p["source_id"]) or {}
        if "original" in p or src.get("original") is False:  # 원문을 못 여는 곳(보안 화면)은 시도하지 않음
            continue
        p["original"] = fetch_original(p["url"], src)


def attach_media(posts: list[dict], cfg: dict, day: str, capture: bool = True, max_images: int = 8) -> None:
    """원문 이미지를 내려받아 저장하고, 필요하면 본문을 캡처함. 실패해도 발행은 계속."""
    from trendbot.collectors import media

    srcs = sources_by_id(cfg)
    for p in posts:
        o = p.get("original")
        if not o or o.get("status") != "ok":
            continue
        src = srcs.get(p["source_id"], {})
        try:
            o["saved"] = media.download_images(o.get("images", [])[:max_images], p["url"], day)
        except Exception:
            o["saved"] = []
        if capture and not o.get("capture") and media.needs_capture(o, o["saved"], src):
            try:
                o["capture"] = media.capture_body(p["url"], (src.get("detail") or {}).get("body"), day)
            except Exception as e:
                o["capture_error"] = e.__class__.__name__


def lifespan(c: Candidate, today: str, now: datetime | None = None) -> dict:
    """이야기 수명: 며칠째인지 + 지금 커지는 중인지(최근 12시간에 새로 올라온 글 비율)."""
    now = now or datetime.now().astimezone()
    seen = sorted(p.data.get("first_seen") for p in c.story.posts if p.data.get("first_seen"))
    starts = [d[:10] for d in seen[:1]] + ([c.first_date] if c.first_date else [])
    first = min(starts) if starts else today
    day = (datetime.fromisoformat(today) - datetime.fromisoformat(first)).days + 1
    recent = (now - timedelta(hours=12)).isoformat()
    fresh = sum(1 for d in seen if d >= recent)
    if seen and fresh / len(seen) >= 0.4:
        trend = "up"
    elif seen and fresh == 0 and day >= 2:
        trend = "down"
    else:
        trend = "flat"
    label = {"up": "확산 중 ↑", "flat": "유지", "down": "식는 중 ↓"}[trend]
    return {"day": max(day, 1), "trend": trend, "label": ("새로 뜸" if day <= 1 and trend == "up" else f"{max(day, 1)}일째 · {label}")}


def _card(c: Candidate, subs: list[Candidate], cfg: dict, fetch_context: bool) -> dict:
    srcs = sources_by_id(cfg)
    posts = sorted(c.story.posts, key=lambda i: (i.data.get("first_seen") or ""))
    path, seen_src = [], set()
    for p in posts:
        if p.source_id not in seen_src:
            seen_src.add(p.source_id)
            path.append({"name": srcs[p.source_id]["name"], "at": (p.data.get("first_seen") or "")[11:16]})
    post_rows = [{
        "source_id": p.source_id, "source_name": srcs[p.source_id]["name"], "title": p.title, "url": p.url,
        "views": p.data.get("views"), "likes": p.data.get("likes"), "comments": p.data.get("comments"),
        "rank": p.data.get("best_rank"),
    } for p in sorted(c.story.posts, key=lambda i: (
        # 대표 글은 원문 내용(본문·이미지)을 가져올 수 있는 사이트 글을 먼저 (펨코·인티·82쿡처럼 제목만 되는 곳은 뒤로)
        srcs[i.source_id].get("original") is False, i.data.get("best_rank") or 99))]
    videos = [{"title": i.title, "url": i.url, "views": i.data.get("value"),
               "channel": i.data.get("extra", {}).get("channel"), "shorts": i.data.get("extra", {}).get("shorts")}
              for i in c.story.items if i.kind == "youtube"]
    news = [i.title for i in c.story.items if i.kind == "news"]
    for i in c.story.items:
        if i.kind == "trend":
            news += [n["title"] for n in i.data.get("extra", {}).get("news", []) if n.get("title")]
    hints = [srcs[p["source_id"]].get("field_hint") for p in post_rows if srcs[p["source_id"]].get("field_hint")]
    if fetch_context:
        attach_originals(post_rows[:2], cfg)
    snippets = [p["original"]["body"][:600] for p in post_rows[:2] if p.get("original", {}).get("body")]
    return {
        "id": c.id, "grade": c.grade, "grade_label": c.badges[1] if c.badges[0] in ("NEW", "업데이트") else c.badges[0],
        "badges": c.badges, "score": c.score, "anchor": c.story.anchor,
        "pods": sorted(c.pods), "tokens": sorted(c.story.toks)[:40],
        "evidence_line": _evidence_line(c, cfg), "age": _age_label(c, cfg),
        "path": path, "posts": post_rows[:6], "videos": videos[:3], "news": news[:6], "snippets": snippets,
        # 사이트 성격 힌트는 글이 모두 그 사이트일 때만 (보배드림 글이 하나 섞였다고 '자동차'가 되지 않게)
        "field_hint": hints[0] if hints and len(hints) == len(post_rows) else None,
        "spread": {"sites": len(seen_src), "pods": len(c.pods), "traffic": c.traffic},
        "subs": [{"title": (s.story.posts[0].title if s.story.posts else s.story.anchor or ""),
                  "evidence": _evidence_line(s, cfg)} for s in subs],
    }


def channel_tops(posts: list[dict], cfg: dict) -> dict[str, dict]:
    """채널마다 조회·댓글·좋아요 각각의 1위 (채널 페이지용, 제목·링크·수치만)."""
    out: dict[str, dict] = {}
    for src in cfg["sources"]:
        mine = [p for p in posts if p["source_id"] == src["id"]]
        if not mine:
            continue
        tops = {}
        for metric in ("views", "comments", "likes"):
            best = max(mine, key=lambda p: p.get(metric) or 0)
            if best.get(metric):
                tops[metric] = {k: best.get(k) for k in ("title", "url", "views", "comments", "likes")}
        out[src["id"]] = tops
    return out


def build_edition(db: sqlite3.Connection, cfg: dict, date: str | None = None, use_ai: bool = True,
                  fetch_context: bool = True, fetch_media: bool = True) -> dict:
    now = datetime.now().astimezone()
    date = date or now.date().isoformat()
    since = (now - timedelta(hours=cfg["grading"]["window_hours"])).isoformat()
    posts = storage.window_posts(db, since)
    signals = storage.window_signals(db, since)

    items = cl.build_items(posts, signals, cfg.get("aliases") or {}, cfg.get("routine_keywords") or [])
    stories = cl.cluster(items)
    published = storage.recent_published(db, date)
    groups = select(stories, cfg, published)

    cards = [_card(c, subs, cfg, fetch_context) for c, subs in groups[:30]]
    for card, (c, _subs) in zip(cards, groups[:30]):
        card["life"] = lifespan(c, date, now)
    if fetch_context and fetch_media:
        attach_media([c["posts"][0] for c in cards if c["posts"]], cfg, date, capture=False, max_images=3)
    results, ai_error = editor.edit(cards) if use_ai else ({}, "AI 사용 안 함")
    cards = [editor.apply(c, results.get(c["id"])) for c in cards]
    excluded = [c for c in cards if c["exclude"] != "없음"]
    cards = [c for c in cards if c["exclude"] == "없음"]

    # 상한: 전체 장수 + 분야별 상한 (모든 등급에 적용)
    g = cfg["grading"]
    caps = dict(g.get("field_caps") or {})
    final, overflow, used = [], [], {}
    for c in sorted(cards, key=lambda c: (GRADE_ORDER[c["grade"]], -c["score"])):
        f = c["field"]
        if len(final) >= g["max_cards"] or (f in caps and used.get(f, 0) >= caps[f]):
            overflow.append(c)
            continue
        used[f] = used.get(f, 0) + 1
        final.append(c)

    in_card = {p["url"]: i + 1 for i, c in enumerate(final) for p in c["posts"]}
    shown = storage.shown_champion_urls(db, date)
    history = {s["id"]: storage.champion_scores(db, s["id"], date) for s in cfg["sources"]}
    champs = champions(posts, cfg, shown, history)
    srcs = sources_by_id(cfg)
    for ch in champs:
        if ch["post"]:
            ch["in_card"] = in_card.get(ch["post"]["url"])
            ch["post"] = {**ch["post"], "source_name": srcs[ch["source_id"]]["name"]}
    if fetch_context:
        attach_originals([ch["post"] for ch in champs if ch["post"] and not ch.get("in_card")], cfg)
    if fetch_context and fetch_media:  # 최종 발행되는 글만 이미지 전체 저장·캡처
        attach_media([p for c in final for p in c["posts"][:2]]
                     + [ch["post"] for ch in champs if ch["post"] and not ch.get("in_card")], cfg, date)

    # 유튜브 1위 (검색 발견 기준)
    yt = [s for s in signals if s["kind"] == "youtube"]
    if yt and cfg["signals"]["youtube"].get("champion"):
        top = max(yt, key=lambda s: s.get("value") or 0)
        champs.append({"source_id": "youtube", "name": "유튜브 인기", "score": top.get("value") or 0,
                       "strength": "쇼츠" if top["extra"].get("shorts") else None,
                       "post": {"title": top["title"], "url": top["url"], "views": top.get("value"),
                                "likes": top["extra"].get("likes"), "comments": top["extra"].get("comments")}})

    # X 트렌드 1위 (가장 최근 수집 기준)
    xt = [s for s in signals if s["kind"] == "x_trend"]
    if xt and cfg["signals"].get("x_trends", {}).get("champion"):
        top = max(xt, key=lambda s: (s.get("value") or 0, s.get("first_at") or ""))
        champs.append({"source_id": "x_trends", "name": "X 트렌드", "score": top.get("value") or 0, "strength": None,
                       "post": {"title": top["extra"].get("tag") or top["title"], "url": top["url"]}})

    # 인스타 1위 (감시 계정 중 평소 대비 가장 크게 튄 게시물)
    ig = [s for s in signals if s["kind"] == "insta"]
    if ig:
        top = max(ig, key=lambda s: s["extra"].get("ratio") or 0)
        champs.append({"source_id": "instagram", "name": "인스타", "score": top.get("value") or 0,
                       "strength": f"평소 {top['extra'].get('ratio')}배",
                       "post": {"title": f"@{top['extra'].get('account')} {top['title']}", "url": top["url"],
                                "likes": top["extra"].get("likes"), "comments": top["extra"].get("comments")}})

    health = storage.source_health(db, since)
    enabled = [s for s in cfg["sources"] if s.get("enabled", True)]
    broken = [{"name": s["name"], "message": health.get(s["id"], {}).get("message") or "수집 기록 없음"}
              for s in enabled if not health.get(s["id"], {}).get("ok")]

    past = [e for e in storage.load_editions(db) if e["date"] < date][:28]
    avg = round(sum(len(e["cards"]) for e in past) / len(past)) if past else None
    if avg is None:
        mood = None
    elif len(final) <= max(2, avg * 0.5):
        mood = "조용한 날"
    elif len(final) >= avg * 1.5:
        mood = "바쁜 날"
    else:
        mood = "평소 수준"

    return {
        "date": date, "generated_at": now_iso(), "cards": final,
        "overflow": [{"id": c["id"], "headline": c["headline"], "evidence": c["evidence_line"]} for c in overflow[: g["overflow_lines"]]],
        "excluded": [{"id": c["id"], "headline": c["headline"], "reason": c["exclude"]} for c in excluded],
        "champions": champs, "channel_tops": channel_tops(posts, cfg), "avg28": avg, "mood": mood,
        "health": {"total": len(enabled), "ok": len(enabled) - len(broken), "broken": broken},
        "ai": {"used": bool(results), "model": editor.MODEL if results else None, "note": ai_error},
        "sample": False,
    }

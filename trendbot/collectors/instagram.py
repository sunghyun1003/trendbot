"""인스타그램 감시 계정 (공식 API: Business Discovery).

config/watchlists/instagram.txt 의 계정마다 최근 게시물 12개를 읽어,
계정 평소(중앙값) 대비 반응(좋아요+댓글)이 RATIO배 이상인 최근 24시간 게시물만 신호로 돌려줍니다.
키: META_ACCESS_TOKEN(만료 없는 페이지 토큰), IG_USER_ID(내 비즈니스 계정 번호). 없으면 빈 목록.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from statistics import median

import httpx

from trendbot.config import ROOT
from trendbot.models import Signal

GRAPH = "https://graph.facebook.com/v21.0"
WATCHLIST = ROOT / "config" / "watchlists" / "instagram.txt"
RATIO = 3.0


def configured() -> bool:
    return bool(os.environ.get("META_ACCESS_TOKEN") and os.environ.get("IG_USER_ID"))


def watchlist(path=WATCHLIST) -> list[str]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        u = line.split("#", 1)[0].strip().lstrip("@")
        if u and u not in out:
            out.append(u)
    return out


def spikes(username: str, media: list[dict], now: datetime | None = None) -> list[Signal]:
    now = now or datetime.now(timezone.utc)
    eng = [(m.get("like_count") or 0) + (m.get("comments_count") or 0) for m in media]
    if len(eng) < 4:
        return []
    base = max(median(eng), 1)
    out = []
    for m, e in zip(media, eng):
        try:
            at = datetime.strptime(m["timestamp"], "%Y-%m-%dT%H:%M:%S%z")
        except (KeyError, ValueError):
            continue
        if now - at > timedelta(hours=24) or e < base * RATIO:
            continue
        caption = (m.get("caption") or "").strip().splitlines()
        out.append(Signal(kind="insta", title=(caption[0] if caption else f"@{username} 게시물")[:120],
                          url=m.get("permalink") or "", value=e,
                          extra={"account": username, "ratio": round(e / base, 1), "likes": m.get("like_count"),
                                 "comments": m.get("comments_count"), "media_type": m.get("media_type")}))
    return out


def collect(cfg: dict, client: httpx.Client | None = None) -> tuple[list[Signal], list[str]]:
    """(신호, 읽지 못한 계정 목록)."""
    if not configured():
        return [], []
    c = client or httpx.Client(timeout=30)
    token, me = os.environ["META_ACCESS_TOKEN"], os.environ["IG_USER_ID"]
    fields = "media.limit(12){caption,like_count,comments_count,timestamp,permalink,media_type}"
    out, failed = [], []
    for u in watchlist():
        r = c.get(f"{GRAPH}/{me}", params={"fields": f"business_discovery.username({u}){{{fields}}}",
                                           "access_token": token})
        if r.status_code != 200:
            failed.append(u)
            continue
        media = ((r.json().get("business_discovery") or {}).get("media") or {}).get("data") or []
        out += spikes(u, media)
    return out, failed

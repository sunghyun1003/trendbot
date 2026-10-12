"""검색·뉴스·영상 신호: 구글 트렌드 RSS, 구글 뉴스 RSS, 유튜브 검색 발견."""

from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

import httpx

from trendbot.collectors.http import USER_AGENT
from trendbot.collectors.numbers import parse_count
from trendbot.models import Signal

HT = "{https://trends.google.com/trending/rss}"


def _get(url: str, params: dict | None = None) -> httpx.Response:
    r = httpx.get(url, params=params, headers={"User-Agent": USER_AGENT}, timeout=20, follow_redirects=True)
    r.raise_for_status()
    return r


def parse_google_trends(xml_text: str) -> list[Signal]:
    root = ET.fromstring(xml_text)
    out: list[Signal] = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        if not title:
            continue
        traffic = item.findtext(f"{HT}approx_traffic") or item.findtext("{*}approx_traffic")
        news = []
        for n in item.iter():
            if n.tag.endswith("news_item"):
                news.append({
                    "title": (n.findtext(f"{HT}news_item_title") or n.findtext("{*}news_item_title") or "").strip(),
                    "url": (n.findtext(f"{HT}news_item_url") or n.findtext("{*}news_item_url") or "").strip(),
                    "source": (n.findtext(f"{HT}news_item_source") or n.findtext("{*}news_item_source") or "").strip(),
                })
        out.append(Signal(kind="google_trends", title=title, value=parse_count(traffic), extra={"news": news[:3]}))
    return out


def parse_google_news(xml_text: str) -> list[Signal]:
    root = ET.fromstring(xml_text)
    out: list[Signal] = []
    for item in root.iter("item"):
        raw = (item.findtext("title") or "").strip()
        press = (item.findtext("source") or "").strip()
        title = re.sub(r"\s+-\s+[^-]+$", "", raw) if press else raw
        out.append(Signal(kind="google_news", title=title, url=(item.findtext("link") or "").strip(),
                          extra={"press": press, "pub": item.findtext("pubDate")}))
    return out


def google_trends(cfg: dict) -> list[Signal]:
    return parse_google_trends(_get(cfg["signals"]["google_trends"]["url"]).text)


def google_news(cfg: dict) -> list[Signal]:
    return parse_google_news(_get(cfg["signals"]["google_news"]["url"]).text)


def _iso_duration_seconds(d: str) -> int:
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", d or "")
    if not m:
        return 0
    days, h, mi, s = (int(x or 0) for x in m.groups())
    return days * 86400 + h * 3600 + mi * 60 + s


def youtube_discovery(cfg: dict) -> list[Signal]:
    """최근 24시간 한국 영상 중 조회순 상위 (API 키가 없으면 빈 목록)."""
    key = os.environ.get("YOUTUBE_API_KEY")
    if not key:
        return []
    ycfg = cfg["signals"]["youtube"]
    since = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
    ids: list[str] = []
    token = None
    for _ in range(ycfg.get("search_pages", 2)):
        params = {"part": "id", "type": "video", "regionCode": "KR", "relevanceLanguage": "ko",
                  "order": "viewCount", "publishedAfter": since, "maxResults": 50, "key": key}
        if token:
            params["pageToken"] = token
        data = _get("https://www.googleapis.com/youtube/v3/search", params).json()
        ids += [i["id"]["videoId"] for i in data.get("items", []) if i.get("id", {}).get("videoId")]
        token = data.get("nextPageToken")
        if not token:
            break
    out: list[Signal] = []
    for start in range(0, len(ids), 50):
        data = _get("https://www.googleapis.com/youtube/v3/videos", {
            "part": "snippet,statistics,contentDetails", "id": ",".join(ids[start:start + 50]), "key": key,
        }).json()
        for v in data.get("items", []):
            sn, st = v["snippet"], v.get("statistics", {})
            secs = _iso_duration_seconds(v.get("contentDetails", {}).get("duration", ""))
            out.append(Signal(
                kind="youtube", title=sn.get("title", ""), url=f"https://www.youtube.com/watch?v={v['id']}",
                value=int(st.get("viewCount", 0) or 0),
                extra={"video_id": v["id"], "channel": sn.get("channelTitle"), "published": sn.get("publishedAt"),
                       "likes": int(st.get("likeCount", 0) or 0), "comments": int(st.get("commentCount", 0) or 0),
                       "shorts": secs <= ycfg.get("shorts_max_seconds", 180),
                       "lang": sn.get("defaultAudioLanguage") or sn.get("defaultLanguage")},
            ))
    return out

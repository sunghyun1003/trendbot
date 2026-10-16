"""검색·뉴스·영상·SNS 신호.

- 구글 트렌드 RSS, 구글 뉴스 RSS
- 유튜브: 검색 발견(최근 24시간 조회순) + 인기 차트(연예·문화 카테고리만)
- X 실시간 트렌드: getdaytrends.com (공개 집계 사이트, robots.txt 확인)
- 연예 뉴스 랭킹: 다음 연예 '많이 본 뉴스' (robots.txt 허용 확인, 정치·경제 없음)
"""

from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

import httpx

from bs4 import BeautifulSoup

from trendbot.collectors.http import USER_AGENT, polite_get
from trendbot.collectors.numbers import parse_count
from trendbot.models import Signal

HT = "{https://trends.google.com/trending/rss}"


def _get(url: str, params: dict | None = None) -> httpx.Response:
    """공식 API(googleapis.com)가 아니면 robots.txt를 먼저 확인 (허용 안 하면 가져오지 않음)."""
    from urllib.parse import urlparse
    from trendbot.collectors.http import Blocked, robots_allows
    if not urlparse(url).netloc.endswith("googleapis.com") and robots_allows(url) is False:
        raise Blocked(f"robots.txt가 수집을 허용하지 않음: {url}")
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
        out += parse_youtube_videos(data.get("items", []), ycfg.get("shorts_max_seconds", 180))
    return out


# ---- X 실시간 트렌드 ----
def parse_x_trends(html: str, limit: int = 30) -> list[Signal]:
    """getdaytrends 지금 순위 (1~15위, 16위~ 두 표로 나뉨). value = 51 - 순위 (클수록 상위)."""
    rows = BeautifulSoup(html, "html.parser").select("table.trends tr")
    out: list[Signal] = []
    for tr in rows[:limit]:
        a = tr.select_one("td.main a")
        pos = tr.select_one("th.pos")
        if not a:
            continue
        tag = a.get_text(strip=True)
        rank = int(pos.get_text(strip=True)) if pos and pos.get_text(strip=True).isdigit() else len(out) + 1
        out.append(Signal(kind="x_trend", title=tag.lstrip("#").replace("_", " "), url=f"https://x.com/search?q={tag}",
                          value=51 - rank, extra={"tag": tag, "rank": rank}))
    return out


def x_trends(cfg: dict) -> list[Signal]:
    return parse_x_trends(polite_get(cfg["signals"]["x_trends"]["url"]))


# ---- 연예 뉴스 랭킹 ----
def parse_daum_ent(html: str) -> list[Signal]:
    box = BeautifulSoup(html, "html.parser").select_one("div.box_news_ranking")
    out: list[Signal] = []
    for i, li in enumerate(box.select("li") if box else [], 1):
        a, t = li.select_one("a[href]"), li.select_one(".tit_txt")
        if not a or not t:
            continue
        info = [x.get_text(strip=True) for x in li.select(".txt_info")]
        out.append(Signal(kind="ent_news", title=t.get_text(" ", strip=True), url=a["href"], value=11 - i,
                          extra={"press": info[0] if info else "", "rank": i, "section": "연예"}))
    return out


def ent_news(cfg: dict) -> list[Signal]:
    return parse_daum_ent(polite_get(cfg["signals"]["ent_news"]["url"]))


# ---- 유튜브 인기 차트 (연예·문화 카테고리만) ----
def parse_youtube_videos(items: list[dict], shorts_max: int, category: str | None = None) -> list[Signal]:
    out = []
    for v in items:
        sn, st = v["snippet"], v.get("statistics", {})
        secs = _iso_duration_seconds(v.get("contentDetails", {}).get("duration", ""))
        out.append(Signal(
            kind="youtube", title=sn.get("title", ""), url=f"https://www.youtube.com/watch?v={v['id']}",
            value=int(st.get("viewCount", 0) or 0),
            extra={"video_id": v["id"], "channel": sn.get("channelTitle"), "published": sn.get("publishedAt"),
                   "likes": int(st.get("likeCount", 0) or 0), "comments": int(st.get("commentCount", 0) or 0),
                   "shorts": secs <= shorts_max, "chart": category,
                   "lang": sn.get("defaultAudioLanguage") or sn.get("defaultLanguage")},
        ))
    return out


def youtube_chart(cfg: dict) -> list[Signal]:
    key = os.environ.get("YOUTUBE_API_KEY")
    if not key:
        return []
    ccfg = cfg["signals"]["youtube_chart"]
    shorts_max = cfg["signals"]["youtube"].get("shorts_max_seconds", 180)
    out: list[Signal] = []
    for name, cat in ccfg["categories"].items():
        try:
            data = _get("https://www.googleapis.com/youtube/v3/videos", {
                "part": "snippet,statistics,contentDetails", "chart": "mostPopular", "regionCode": "KR",
                "videoCategoryId": cat, "maxResults": ccfg.get("per_category", 20), "key": key,
            }).json()
        except httpx.HTTPStatusError:  # 그 카테고리에 차트가 없으면 건너뜀
            continue
        out += parse_youtube_videos(data.get("items", []), shorts_max, name)
    return out

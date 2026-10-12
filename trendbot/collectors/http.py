"""예의 바른 가져오기: robots.txt 확인, 사이트별 간격, 짧은 시간 제한."""

from __future__ import annotations

import time
import urllib.robotparser
from urllib.parse import urlparse

import httpx

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/129.0 Safari/537.36 trendbot-internal/0.1"
)
MIN_INTERVAL_SEC = 3.0

_last_hit: dict[str, float] = {}
_robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}


class Blocked(Exception):
    """robots.txt 금지, 차단(403/429), 봇 확인 화면 등."""


def _client() -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": USER_AGENT, "Accept-Language": "ko-KR,ko;q=0.9"},
        timeout=20,
        follow_redirects=True,
    )


def robots_allows(url: str, client: httpx.Client | None = None) -> bool | None:
    """True/False, 또는 robots.txt를 못 읽으면 None."""
    host = urlparse(url)
    base = f"{host.scheme}://{host.netloc}"
    if base not in _robots:
        rp = urllib.robotparser.RobotFileParser()
        try:
            c = client or _client()
            r = c.get(base + "/robots.txt")
            if r.status_code >= 400:
                _robots[base] = None
            else:
                rp.parse(r.text.splitlines())
                _robots[base] = rp
        except httpx.HTTPError:
            _robots[base] = None
    rp = _robots[base]
    if rp is None:
        return None
    return rp.can_fetch("*", url)


def polite_get(url: str, client: httpx.Client | None = None, check_robots: bool = True) -> str:
    c = client or _client()
    if check_robots and robots_allows(url, c) is False:
        raise Blocked(f"robots.txt가 수집을 허용하지 않음: {url}")
    host = urlparse(url).netloc
    wait = MIN_INTERVAL_SEC - (time.monotonic() - _last_hit.get(host, 0))
    if wait > 0:
        time.sleep(wait)
    _last_hit[host] = time.monotonic()
    r = c.get(url)
    if r.status_code in (403, 429, 503):
        raise Blocked(f"차단 응답 {r.status_code}: {url}")
    r.raise_for_status()
    text = r.text
    lowered = text[:5000].lower()
    if any(m in lowered for m in ("captcha", "challenge-platform", "cf-chl", "are you a robot")):
        raise Blocked(f"봇 확인 화면이 나옴: {url}")
    return text

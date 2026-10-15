"""설정(sources.yaml)의 선택자로 베스트 목록 페이지를 읽는 범용 수집기."""

from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from trendbot.collectors.http import polite_get
from trendbot.collectors.numbers import parse_count
from trendbot.models import Post

MAX_ROWS = 20
ROWS_BY_POWER = {3: 50, 2: 30, 1: 20}  # 화력이 센 사이트는 목록을 더 깊이 읽음 (한 화면에 있는 만큼만)
AD_PATTERNS = [r"^AD\s", r"^\[?광고\]?", r"^\[?공지\]?"]


def _select(row: Tag, spec: str) -> str | None:
    """'css' → 글자, 'css@attr' → 속성값, 'css!2' → 세 번째로 맞는 요소. 쉼표로 여러 후보."""
    for candidate in spec.split(","):
        candidate = candidate.strip()
        attr, idx = None, 0
        if "@" in candidate:
            candidate, attr = candidate.rsplit("@", 1)
        if "!" in candidate:
            candidate, n = candidate.rsplit("!", 1)
            idx = int(n)
        found = row.select(candidate) if candidate else [row]
        el = found[idx] if len(found) > idx else None
        if el is None:
            continue
        if attr:
            val = el.get(attr)
            if val:
                return str(val).strip()
        else:
            txt = el.get_text(" ", strip=True)
            if txt:
                return txt
    return None


def parse_list(html: str, source: dict) -> list[Post]:
    soup = BeautifulSoup(html, "html.parser")
    fields = source["fields"]
    limit = source.get("max_rows") or ROWS_BY_POWER.get(source.get("power", 1), MAX_ROWS)
    posts: list[Post] = []
    seen_urls: set[str] = set()
    for row in soup.select(source["row"]):
        href = _select(row, fields["link"])
        nums = {k: parse_count(_select(row, fields[k])) if k in fields else None for k in ("views", "likes", "comments")}
        posted = _select(row, fields["posted"]) if "posted" in fields else None
        for junk in source.get("strip", []):  # 제목 안에 섞인 댓글 수·아이콘 제거
            for el in row.select(junk):
                el.decompose()
        title = _select(row, fields["title"])
        if not title or not href or href.startswith("javascript"):
            continue
        if any(re.search(pat, title) for pat in source.get("title_exclude", AD_PATTERNS)):
            continue
        url = urljoin(source["url"], href)
        if rw := source.get("link_rewrite"):  # 모아보기 사이트를 거칠 때 원래 글 주소로 바꿈
            url = re.sub(rw["pattern"], rw["to"], url)
        if url in seen_urls:
            continue
        seen_urls.add(url)
        posts.append(
            Post(
                source_id=source["id"],
                title=" ".join(title.split()),
                url=url,
                rank=len(posts) + 1,
                views=nums["views"], likes=nums["likes"], comments=nums["comments"], posted_at=posted,
            )
        )
        if len(posts) >= limit:
            break
    return posts


def collect(source: dict) -> list[Post]:
    return parse_list(polite_get(source["url"]), source)

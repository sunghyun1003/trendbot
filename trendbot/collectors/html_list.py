"""설정(sources.yaml)의 선택자로 베스트 목록 페이지를 읽는 범용 수집기."""

from __future__ import annotations

from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from trendbot.collectors.http import polite_get
from trendbot.collectors.numbers import parse_count
from trendbot.models import Post

MAX_ROWS = 20


def _select(row: Tag, spec: str) -> str | None:
    """'css' → 글자, 'css@attr' → 속성값. 쉼표로 여러 후보를 줄 수 있음."""
    for candidate in spec.split(","):
        candidate = candidate.strip()
        attr = None
        if "@" in candidate:
            candidate, attr = candidate.rsplit("@", 1)
        el = row.select_one(candidate) if candidate else row
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
    posts: list[Post] = []
    seen_urls: set[str] = set()
    for row in soup.select(source["row"]):
        title = _select(row, fields["title"])
        href = _select(row, fields["link"])
        if not title or not href:
            continue
        url = urljoin(source["url"], href)
        if url in seen_urls:
            continue
        seen_urls.add(url)
        posts.append(
            Post(
                source_id=source["id"],
                title=" ".join(title.split()),
                url=url,
                rank=len(posts) + 1,
                views=parse_count(_select(row, fields["views"])) if "views" in fields else None,
                likes=parse_count(_select(row, fields["likes"])) if "likes" in fields else None,
                comments=parse_count(_select(row, fields["comments"])) if "comments" in fields else None,
                posted_at=_select(row, fields["posted"]) if "posted" in fields else None,
            )
        )
        if len(posts) >= MAX_ROWS:
            break
    return posts


def collect(source: dict) -> list[Post]:
    return parse_list(polite_get(source["url"]), source)

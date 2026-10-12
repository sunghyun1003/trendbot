"""같은 이야기를 다룬 글·검색어·영상을 하나로 묶습니다.

묶는 기준 (위에서부터 강한 순):
1. 같은 링크 / 같은 유튜브 영상
2. 구글 트렌드 검색어(앵커)가 제목에 들어 있음
3. 서로 다른 사이트의 제목이 '흔하지 않은 낱말'을 2개 이상 공유
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

# 커뮤니티 제목에 흔히 붙지만 이야기를 구분하지 못하는 말
STOPWORDS = {
    "오늘", "오늘자", "어제", "근황", "레전드", "실화", "논란", "후기", "사진", "영상", "이유", "정리", "현재",
    "진짜", "역대급", "충격", "반응", "상황", "결국", "공개", "속보", "단독", "이거", "그냥", "이번", "드디어",
    "jpg", "gif", "png", "mp4", "펌", "스압", "ㅋㅋ", "ㅋㅋㅋ", "ㄷㄷ", "ㅎㅎ", "있는", "없는", "하는", "했다",
    "한다", "에서", "까지", "우리", "사람", "남자", "여자", "한국", "때문", "보고", "보는", "같은", "the", "and",
}
JOSA = ("에서는", "에게서", "으로는", "이라는", "에서", "에게", "한테", "으로", "까지", "부터", "처럼", "보다",
        "이랑", "라는", "하는", "했던", "은", "는", "이", "가", "을", "를", "의", "에", "로", "와", "과", "도", "만", "랑")
_TOKEN = re.compile(r"[가-힣]{2,}|[A-Za-z][A-Za-z0-9]{1,}|\d{2,}[가-힣A-Za-z]*")
_YT = re.compile(r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([\w-]{11})")


def normalize(text: str) -> str:
    return re.sub(r"[\s\W_]+", "", text.lower())


def _strip_josa(tok: str) -> str:
    for j in JOSA:
        if len(tok) > len(j) + 1 and tok.endswith(j):
            return tok[: -len(j)]
    return tok


def tokens(title: str, aliases: dict[str, list[str]] | None = None) -> set[str]:
    text = title
    for canon, alts in (aliases or {}).items():
        for a in alts:
            text = text.replace(a, canon)
    out = set()
    for t in _TOKEN.findall(text):
        t = _strip_josa(t.lower())
        if len(t) >= 2 and t not in STOPWORDS:
            out.add(t)
    return out


def link_key(url: str) -> str:
    m = _YT.search(url or "")
    if m:
        return "yt:" + m.group(1)
    return "url:" + re.sub(r"[?#].*$", "", (url or "").rstrip("/"))


@dataclass
class Item:
    kind: str  # post | trend | news | youtube
    source_id: str
    title: str
    url: str
    data: dict
    toks: set[str] = field(default_factory=set)


@dataclass
class Story:
    items: list[Item]
    anchor: str | None = None

    @property
    def posts(self) -> list[Item]:
        return [i for i in self.items if i.kind == "post"]

    @property
    def toks(self) -> set[str]:
        out: set[str] = set()
        for i in self.items:
            out |= i.toks
        return out


class _UF:
    def __init__(self, n: int):
        self.p = list(range(n))
        self.size = [1] * n

    def find(self, x: int) -> int:
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a: int, b: int, max_size: int = 40) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra == rb or self.size[ra] + self.size[rb] > max_size:
            return
        if self.size[ra] < self.size[rb]:
            ra, rb = rb, ra
        self.p[rb] = ra
        self.size[ra] += self.size[rb]


def build_items(posts: list[dict], signals: list[dict], aliases: dict, routine: list[str]) -> list[Item]:
    items: list[Item] = []
    for p in posts:
        items.append(Item("post", p["source_id"], p["title"], p["url"], p, tokens(p["title"], aliases)))
    for s in signals:
        if any(r in s["title"] for r in routine):
            continue
        kind = {"google_trends": "trend", "google_news": "news", "youtube": "youtube"}.get(s["kind"], s["kind"])
        items.append(Item(kind, s["kind"], s["title"], s.get("url") or "", s, tokens(s["title"], aliases)))
    return items


def cluster(items: list[Item]) -> list[Story]:
    n = len(items)
    uf = _UF(n)

    # 1. 같은 링크/영상
    by_link: dict[str, int] = {}
    for i, it in enumerate(items):
        if not it.url:
            continue
        k = link_key(it.url)
        if k in by_link:
            uf.union(by_link[k], i)
        else:
            by_link[k] = i

    # 2. 구글 트렌드 검색어 앵커
    anchors = [(i, normalize(it.title)) for i, it in enumerate(items) if it.kind == "trend" and len(normalize(it.title)) >= 2]
    for i, it in enumerate(items):
        if it.kind == "trend":
            continue
        norm = normalize(it.title)
        for ai, akey in anchors:
            if akey and akey in norm:
                uf.union(ai, i)

    # 3. 흔하지 않은 낱말 2개 이상 공유 (다른 출처끼리)
    df = Counter(t for it in items for t in it.toks)
    rare_max = max(3, int(n * 0.02))
    rare = [{t for t in it.toks if df[t] <= rare_max} for it in items]
    postings: dict[str, list[int]] = {}
    for i, rs in enumerate(rare):
        for t in rs:
            postings.setdefault(t, []).append(i)
    pair_shared: Counter = Counter()
    for t, idxs in postings.items():
        if len(idxs) < 2:
            continue
        for x in range(len(idxs)):
            for y in range(x + 1, len(idxs)):
                a, b = idxs[x], idxs[y]
                if items[a].source_id != items[b].source_id:
                    pair_shared[(a, b)] += 1
    for (a, b), c in pair_shared.items():
        if c >= 2:
            uf.union(a, b)

    groups: dict[int, list[Item]] = {}
    for i, it in enumerate(items):
        groups.setdefault(uf.find(i), []).append(it)
    stories = []
    for members in groups.values():
        anchor = next((m.title for m in members if m.kind == "trend"), None)
        stories.append(Story(members, anchor))
    return stories

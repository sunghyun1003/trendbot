"""모든 수집기가 공통으로 돌려주는 데이터 형식."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime


@dataclass
class Post:
    """베스트 목록에서 본 글 한 줄 (본문·닉네임은 담지 않음)."""

    source_id: str
    title: str
    url: str
    rank: int
    views: int | None = None
    likes: int | None = None
    comments: int | None = None
    posted_at: str | None = None
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Signal:
    """검색·뉴스·영상 신호 (구글 트렌드 키워드, 뉴스 기사, 유튜브 영상 등)."""

    kind: str  # google_trends | google_news | youtube
    title: str
    url: str = ""
    value: int | None = None  # 트래픽, 조회수 등
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")

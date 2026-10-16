from pathlib import Path

from trendbot.collectors import signals
from trendbot.pipeline.cluster import build_items, cluster
from trendbot.pipeline.grade import _pods_of

FIX = Path(__file__).parent / "fixtures"


def test_x_trends_parse():
    sig = signals.parse_x_trends((FIX / "x_trends.html").read_text(encoding="utf-8"))
    assert len(sig) >= 20
    assert sig[0].extra["rank"] == 1 and sig[0].value == 50 and sig[0].extra["tag"].startswith("#")
    assert all("_" not in s.title and not s.title.startswith("#") for s in sig)


def test_daum_ent_ranking_parse():
    sig = signals.parse_daum_ent((FIX / "daum_ent.html").read_text(encoding="utf-8"))
    assert len(sig) == 10
    assert sig[0].extra["rank"] == 1 and sig[0].url.startswith("https://v.daum.net/v/")
    assert sig[0].title and sig[0].extra["press"]


def test_youtube_chart_only_culture_categories(monkeypatch):
    calls = []

    class R:
        def __init__(self, cat):
            self.cat = cat

        def json(self):
            return {"items": [{"id": f"vid{self.cat}xxxxx"[:11], "snippet": {"title": f"영상 {self.cat}"},
                               "statistics": {"viewCount": "1000"}, "contentDetails": {"duration": "PT3M"}}]}

    def fake_get(url, params=None):
        calls.append(params["videoCategoryId"])
        return R(params["videoCategoryId"])

    monkeypatch.setenv("YOUTUBE_API_KEY", "k")
    monkeypatch.setattr(signals, "_get", fake_get)
    cfg = {"signals": {"youtube": {"shorts_max_seconds": 180},
                       "youtube_chart": {"categories": {"음악": "10", "엔터테인먼트": "24"}}}}
    out = signals.youtube_chart(cfg)
    assert calls == ["10", "24"] and "25" not in calls  # 뉴스·정치(25)는 부르지 않음
    assert [s.extra["chart"] for s in out] == ["음악", "엔터테인먼트"]


def test_x_trend_keyword_joins_story_and_adds_sns_pod():
    posts = [{"source_id": "theqoo", "title": "지민 생일 서포트 규모 미쳤다", "url": "https://theqoo.net/1", "views": 1},
             {"source_id": "dcbest", "title": "오늘 점심 뭐먹지", "url": "https://dc/1", "views": 1}]
    sigs = [{"kind": "x_trend", "title": "지민 생일", "url": "https://x.com/search?q=%23지민생일", "value": 49,
             "extra": {"rank": 2}}]
    stories = cluster(build_items(posts, sigs, {}, []))
    story = next(s for s in stories if any(i.kind == "xtrend" for i in s.items))
    assert [p.source_id for p in story.posts] == ["theqoo"]
    assert "P8" in _pods_of(story, {"theqoo": "P5"})


def test_instagram_spikes_and_watchlist(tmp_path):
    from datetime import datetime, timezone
    from trendbot.collectors import instagram

    wl = tmp_path / "w.txt"
    wl.write_text("# 주석\n@a_mag\nb_meme  # 메모\na_mag\n", encoding="utf-8")
    assert instagram.watchlist(wl) == ["a_mag", "b_meme"]
    now = datetime(2026, 10, 13, 12, tzinfo=timezone.utc)
    media = [{"like_count": 100, "comments_count": 0, "timestamp": "2026-10-01T00:00:00+0000"}] * 6 + [
        {"like_count": 900, "comments_count": 50, "timestamp": "2026-10-13T03:00:00+0000", "caption": "신상 밈\n#태그",
         "permalink": "https://instagram.com/p/x"},
        {"like_count": 800, "comments_count": 0, "timestamp": "2026-10-05T03:00:00+0000"}]  # 오래된 건 제외
    out = instagram.spikes("a_mag", media, now)
    assert len(out) == 1 and out[0].title == "신상 밈" and out[0].extra["ratio"] == 9.5


def test_non_api_fetch_respects_robots(monkeypatch):
    """공식 API가 아닌 주소는 robots.txt가 막으면 가져오지 않음 (구글 뉴스 RSS 사례)."""
    import pytest
    from trendbot.collectors import http, signals
    monkeypatch.setattr(http, "robots_allows", lambda url, client=None: False)
    with pytest.raises(http.Blocked):
        signals._get("https://news.google.com/rss?hl=ko")

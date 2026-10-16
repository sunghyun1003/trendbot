from trendbot.pipeline import cluster as cl
from trendbot.pipeline import context
from trendbot.config import load_config


def _story(*posts):
    return cl.Story([cl.Item("post", sid, t, u, {"best_rank": r}) for sid, t, u, r in posts])


def test_same_story_alt_prefers_site_with_original():
    cfg = load_config()
    content = {s["id"] for s in cfg["sources"] if s.get("original") is not False}
    st = _story(("fmkorea", "인도 양궁이 갑자기 강해진 이유", "https://www.fmkorea.com/1", 1),
                ("ruliweb", "인도 양궁이 갑자기 강해진 이유. (17)", "https://bbs.ruliweb.com/x/2", 3))
    alt = context.same_story_alt({"url": "https://www.fmkorea.com/1"}, [st], content)
    assert alt["source_id"] == "ruliweb" and alt["url"].endswith("/2")
    lone = _story(("instiz", "혼자 뜬 글", "https://www.instiz.net/pt/9", 1))
    assert context.same_story_alt({"url": "https://www.instiz.net/pt/9"}, [lone], content) is None


def test_local_news_needs_two_shared_words():
    signals = [{"kind": "google_news", "title": "한화이글스 류지현 감독 선임, 3년 계약", "url": "u1", "extra": {"press": "A일보"}},
               {"kind": "google_news", "title": "감독 교체 시즌 마무리", "url": "u2", "extra": {}}]
    hits = context.local_news("한화이글스 신임 감독 류지현 확정", signals)
    assert [h["url"] for h in hits] == ["u1"]


def test_enrich_attaches_news_only_when_ai_says_related(monkeypatch):
    cfg = load_config()
    posts = [{"source_id": "instiz", "title": "에버랜드 카피바라 세쌍둥이 공개", "url": "https://www.instiz.net/pt/1"},
             {"source_id": "instiz", "title": "오늘 점심 뭐 먹지 고민", "url": "https://www.instiz.net/pt/2"}]
    news = {"에버랜드 카피바라 세쌍둥이 공개": [{"title": "에버랜드 카피바라 세쌍둥이 첫 공개", "url": "n1", "source": "B뉴스"}],
            "오늘 점심 뭐 먹지 고민": [{"title": "직장인 점심값 고민 늘어", "url": "n2", "source": "C경제"}]}
    monkeypatch.setattr(context, "summarize", lambda items: {0: {"related": True, "summary": "에버랜드가 카피바라 세쌍둥이를 처음 공개했다."},
                                                             1: {"related": False, "summary": ""}})
    context.enrich(posts, [], [], cfg, use_ai=True, search=lambda t: news[t])
    assert posts[0]["news_ctx"]["summary"].startswith("에버랜드") and posts[0]["news_ctx"]["articles"][0]["url"] == "n1"
    assert "news_ctx" not in posts[1]   # 낱말만 겹친 엉뚱한 기사는 붙이지 않음


def test_naver_news_search_cleans_tags_and_needs_keys(monkeypatch):
    monkeypatch.delenv("NAVER_CLIENT_ID", raising=False)
    assert context.search_news("에버랜드 카피바라 세쌍둥이 공개") == []
    monkeypatch.setenv("NAVER_CLIENT_ID", "id")
    monkeypatch.setenv("NAVER_CLIENT_SECRET", "sec")
    seen = {}
    class R:
        def raise_for_status(self): pass
        def json(self): return {"items": [{"title": "<b>에버랜드</b> 카피바라 &quot;세쌍둥이&quot;", "originallink": "https://n/1",
                                           "description": "첫 <b>공개</b>"}]}
    def get(url, params, headers, timeout):
        seen.update(url=url, q=params["query"], h=headers)
        return R()
    out = context.search_news("에버랜드 카피바라 세쌍둥이 공개", get=get)
    assert out == [{"title": '에버랜드 카피바라 "세쌍둥이"', "url": "https://n/1", "source": "", "desc": "첫 공개"}]
    assert seen["url"].startswith("https://openapi.naver.com/v1/search/news") and seen["h"]["X-Naver-Client-Id"] == "id"

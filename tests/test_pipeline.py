"""견본 데이터로 판정 엔진의 규칙을 확인합니다 (AI·네트워크 없이)."""

from datetime import datetime, timedelta

from trendbot import storage
from trendbot.config import load_config
from trendbot.models import Post, Signal
from trendbot.pipeline.edition import build_edition


def _db(tmp_path):
    return storage.connect(tmp_path / "t.db")


def _seed(db, at, extra=()):
    posts = [
        # 같은 이야기: 남초(P1, P3) + 여초(P5, P6) → A 전국구
        Post("dcbest", "구름빵크림 편의점 세 군데 다 품절", "https://d/1", 1, 180000, 2100, 640),
        Post("ppomppu_hot", "구름빵크림 편의점 재고 품절 정보", "https://p/1", 2, 31000, 45, 260),
        Post("theqoo", "구름빵크림 먹어본 후기 편의점 품절", "https://q/1", 1, 81000, None, 1203),
        Post("instiz", "요즘 구름빵크림 때문에 편의점 알바 힘들다", "https://n/1", 3, 52000, 310, 420),
        # 남초 2곳만 → 검색 신호 없으면 탈락
        Post("bobaedream", "새 노트북 배터리 실측 결과", "https://c/1", 1, 21000, 140, 230),
        Post("ruliweb", "노트북 배터리 실측 대결", "https://r/1", 4, 9000, 30, 40),
        # 아무 데도 안 퍼진 글
        Post("cook82", "김장 비용 올해 얼마나 드셨어요", "https://k/1", 1, 15000, None, 180),
        *extra,
    ]
    storage.save_posts(db, posts, at)
    storage.save_signals(db, [Signal("google_trends", "구름빵크림", value=50000)], at)
    for s in ("dcbest", "ppomppu_hot", "theqoo", "instiz", "bobaedream", "ruliweb", "cook82"):
        storage.log_run(db, s, True, 1)


def test_spread_gate_and_champions(tmp_path):
    cfg = load_config()
    db = _db(tmp_path)
    _seed(db, datetime.now().astimezone().isoformat())
    ed = build_edition(db, cfg, date="2026-10-13", use_ai=False, fetch_context=False)
    assert len(ed["cards"]) == 1
    c = ed["cards"][0]
    assert c["grade"] == "A" and "전국 확산" in c["badges"] and "NEW" in c["badges"]
    assert c["spread"]["sites"] == 4
    assert "구글 트렌드" in c["evidence_line"]
    champs = {ch["source_id"]: ch for ch in ed["champions"]}
    assert "cook82" not in champs                      # 82쿡은 신호 전용 (로그인 전용 글이라 1위 탭에 안 보임)
    assert champs["bobaedream"]["post"]["title"].startswith("새 노트북")
    assert champs["dcbest"]["in_card"] == 1


def test_no_repeat_next_day(tmp_path):
    cfg = load_config()
    db = _db(tmp_path)
    now = datetime.now().astimezone()
    _seed(db, (now - timedelta(hours=2)).isoformat())
    day1 = build_edition(db, cfg, date="2026-10-13", use_ai=False, fetch_context=False)
    storage.save_edition(db, day1)
    day2 = build_edition(db, cfg, date="2026-10-14", use_ai=False, fetch_context=False)
    assert day1["cards"] and not day2["cards"]
    # 이미 보여 준 채널 1위도 다시 나오지 않음
    assert all(ch["post"] is None for ch in day2["champions"] if ch["source_id"] == "bobaedream")


def test_card_cap(tmp_path):
    cfg = load_config()
    cfg["grading"]["max_cards"] = 0
    db = _db(tmp_path)
    _seed(db, datetime.now().astimezone().isoformat())
    ed = build_edition(db, cfg, date="2026-10-13", use_ai=False, fetch_context=False)
    assert ed["cards"] == [] and len(ed["overflow"]) == 1


def test_ai_cannot_drop_nationwide_for_soft_reasons():
    from trendbot.pipeline.editor import apply
    card = {"grade": "A", "posts": [{"title": "원제목"}], "evidence_line": "근거"}
    out = apply(dict(card), {"headline": "h", "why": "w", "field": "음식", "attributes": [], "marketer": "없음",
                             "context": "확인", "exclude": "팬덤전용", "caution": False})
    assert out["exclude"] == "없음" and out["caution"] is True
    out = apply(dict(card), {"headline": "h", "why": "w", "field": "음식", "attributes": [], "marketer": "없음",
                             "context": "제목만", "exclude": "광고", "caution": False})
    assert out["exclude"] == "광고" and out["headline"] == "원제목"


def test_board_urls_with_query_are_not_merged():
    from trendbot.pipeline.cluster import link_key
    a = link_key("https://www.ppomppu.co.kr/zboard/zboard.php?id=freeboard&no=1&page=1")
    b = link_key("https://www.ppomppu.co.kr/zboard/zboard.php?id=freeboard&no=2&page=3")
    assert a != b
    assert link_key("https://youtu.be/abcdefghijk") == link_key("https://www.youtube.com/watch?v=abcdefghijk&t=3")


def test_channel_pages_built(tmp_path):
    from trendbot.sample import sample_editions
    from trendbot.site.build import build
    out = build(sample_editions(), [], tmp_path / "site")
    page = (out / "channel" / "ppomppu_hot.html").read_text(encoding="utf-8")
    assert "뽐뿌 HOT" in page and "조회 1위" in page and "러닝화" in page
    assert 'href="channel/ppomppu_hot.html"' in (out / "archive.html").read_text(encoding="utf-8")


def test_unrelated_posts_are_not_chained():
    """A~B, B~C가 조금씩 닮았다고 A와 C까지 한 이야기로 묶지 않음. 흔한 검색어('수술')도 엉뚱한 글을 끌어오지 않음."""
    from trendbot.pipeline import cluster as cl
    posts = [
        {"source_id": "theqoo", "title": "인천 홈플러스 흉기난동 용의자 체포", "url": "u1"},
        {"source_id": "dcbest", "title": "인천 홈플러스 흉기난동 cctv 공개", "url": "u2"},
        {"source_id": "cook82", "title": "유방암 수술한 지인 교수님 왈 체중관리", "url": "u3"},
        {"source_id": "fmkorea", "title": "광희가 성형수술을 한 이유", "url": "u4"},
        {"source_id": "ppomppu_hot", "title": "신한플레이 퀴즈 정답 10월 13일", "url": "u5"},
        {"source_id": "theqoo", "title": "10월 13일 별자리 운세", "url": "u6"},
    ]
    signals = [{"kind": "google_trends", "title": "수술", "url": "", "value": 500,
                "extra": {"news": [{"title": "인천 흉기난동 피해자 수술 끝에 회복"}]}}]
    items = cl.build_items(posts, signals, {}, ["운세", "퀴즈 정답"])
    stories = cl.cluster(items)
    together = [sorted(i.url for i in s.items if i.url) for s in stories if len(s.items) > 1]
    assert ["u1", "u2"] in together
    assert all("u3" not in g and "u4" not in g for g in together)
    assert all(i.url not in ("u5", "u6") for s in stories for i in s.items)


def test_source_power_raises_score():
    """같은 퍼짐이라도 화력 큰 사이트(디시·더쿠)에 올라온 이야기가 작은 사이트보다 점수가 높음."""
    from trendbot.pipeline import cluster as cl
    from trendbot.pipeline.grade import evaluate
    cfg = load_config()
    def story(*sids):
        return cl.Story(cl.build_items([{"source_id": s, "title": "구름빵 크림 품절 대란", "url": f"x{i}"}
                                        for i, s in enumerate(sids)], [], {}, []))
    big = evaluate(story("dcbest", "theqoo", "ruliweb"), cfg)            # 남·여·취미 3곳, 화력 3+3+2
    small = evaluate(story("humoruniv", "cook82", "ppomppu_deal"), cfg)  # 남·여·30대 3곳, 화력 2+1+1
    assert big and small and big.score > small.score


def test_lifespan_labels():
    from datetime import datetime
    from trendbot.pipeline import cluster as cl
    from trendbot.pipeline.edition import lifespan
    from trendbot.pipeline.grade import Candidate
    now = datetime.fromisoformat("2026-10-15T07:00:00+09:00")
    def cand(seen, first_date=None):
        items = [cl.Item("post", "theqoo", "t", f"u{i}", {"first_seen": s}) for i, s in enumerate(seen)]
        c = Candidate(cl.Story(items), "B", set(), set(), False, False, 0, 0, 0, 0, 0)
        c.first_date = first_date
        return c
    assert lifespan(cand(["2026-10-15T01:00:00+09:00", "2026-10-15T03:00:00+09:00"]), "2026-10-15", now)["label"] == "새로 뜸"
    assert lifespan(cand(["2026-10-14T09:00:00+09:00", "2026-10-15T05:00:00+09:00"], "2026-10-13"), "2026-10-15", now)["label"] == "3일째 · 확산 중 ↑"
    assert lifespan(cand(["2026-10-14T09:00:00+09:00", "2026-10-14T10:00:00+09:00"]), "2026-10-15", now)["label"] == "2일째 · 식는 중 ↓"

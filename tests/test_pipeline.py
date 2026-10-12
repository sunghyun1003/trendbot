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
        Post("natepann", "요즘 구름빵크림 때문에 편의점 알바 힘들다", "https://n/1", 3, 52000, 310, 420),
        # 남초 2곳만 → 검색 신호 없으면 탈락
        Post("clien", "새 노트북 배터리 실측 결과", "https://c/1", 1, 21000, 140, 230),
        Post("ruliweb", "노트북 배터리 실측 대결", "https://r/1", 4, 9000, 30, 40),
        # 아무 데도 안 퍼진 글
        Post("cook82", "김장 비용 올해 얼마나 드셨어요", "https://k/1", 1, 15000, None, 180),
        *extra,
    ]
    storage.save_posts(db, posts, at)
    storage.save_signals(db, [Signal("google_trends", "구름빵크림", value=50000)], at)
    for s in ("dcbest", "ppomppu_hot", "theqoo", "natepann", "clien", "ruliweb", "cook82"):
        storage.log_run(db, s, True, 1)


def test_spread_gate_and_champions(tmp_path):
    cfg = load_config()
    db = _db(tmp_path)
    _seed(db, datetime.now().astimezone().isoformat())
    ed = build_edition(db, cfg, date="2026-10-13", use_ai=False, fetch_context=False)
    assert len(ed["cards"]) == 1
    c = ed["cards"][0]
    assert c["grade"] == "A" and "전국구" in c["badges"] and "NEW" in c["badges"]
    assert c["spread"]["sites"] == 4
    assert "구글 트렌드" in c["evidence_line"]
    champs = {ch["source_id"]: ch for ch in ed["champions"]}
    assert champs["cook82"]["post"]["title"].startswith("김장")
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
    assert all(ch["post"] is None for ch in day2["champions"] if ch["source_id"] == "cook82")


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

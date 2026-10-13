from pathlib import Path

from trendbot import benchmark

FIX = Path(__file__).parent / "fixtures"


def test_parse_issuelink_all():
    rows = benchmark.parse((FIX / "issuelink_all.html").read_text(encoding="utf-8"))
    assert len(rows) == 100
    r = rows[0]
    assert r["code"] and r["title"] and "[" not in r["title"][-4:] and r["views"]


def test_same_title_loose_match():
    assert benchmark.same("아시안게임 군면제 관련 새로운 이슈.jpg", "아시안게임 군면제 관련 새로운 이슈")
    assert benchmark.same("이수만이 만든 새 걸그룹 나이 [17]", "이수만이 만든 새 걸그룹 나이")
    assert not benchmark.same("오늘 점심 메뉴", "이수만이 만든 새 걸그룹 나이")


def test_compare_counts_and_excludes_refused_sites():
    ranked = [
        {"code": "clien", "title": "클리앙 글", "views": 9, "comments": 1},       # 원래 사이트가 거부 → 비교 제외
        {"code": "fmkorea", "title": "펨코 대박 글", "views": 9000, "comments": 30},
        {"code": "theqoo", "title": "더쿠 화제 글", "views": 8000, "comments": 20},
        {"code": "inven", "title": "인벤 놓친 글", "views": 7000, "comments": 10},
    ]
    edition = {"cards": [{"posts": [{"source_id": "fmkorea", "title": "펨코 대박 글.jpg"}]}],
               "champions": [{"post": None}]}
    collected = [{"source_id": "fmkorea", "title": "펨코 대박 글"}, {"source_id": "theqoo", "title": "더쿠 화제 글"}]
    b = benchmark.compare(ranked, edition, collected)
    assert b["total"] == 3 and b["collected"] == 2 and b["in_edition"] == 1
    assert [m["title"] for m in b["missed"]] == ["더쿠 화제 글", "인벤 놓친 글"]
    assert b["missed"][0]["collected"] is True and b["missed"][1]["collected"] is False

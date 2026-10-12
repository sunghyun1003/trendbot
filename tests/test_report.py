from trendbot import report


def test_render_counts_sources_and_originals():
    src = [{"name": "루리웹", "state": "정상", "posts": 20, "views": "100%", "likes": "100%", "comments": "100%", "top": "글"},
           {"name": "더쿠", "state": "실패: 403", "posts": 0, "views": "-", "likes": "-", "comments": "-", "top": ""},
           {"name": "클리앙", "state": "꺼짐", "posts": 0, "views": "-", "likes": "-", "comments": "-", "top": ""}]
    edition = {"cards": [], "champions": [{"name": "루리웹", "post": {
        "title": "제목", "source_name": "루리웹",
        "original": {"status": "ok", "body": "본문", "images": ["a"], "saved": [], "capture": ["c"], "comments": [{"text": "x"}]}}}]}
    text = report.render(src, report.original_rows(edition), edition)
    assert "켜진 사이트 2곳 중 1곳 정상" in text
    assert "| 루리웹 | 제목 | ok | 2 | 1 | 0 | 1 | 1 |" in text
    assert "원문 1개 중 1개 성공" in text

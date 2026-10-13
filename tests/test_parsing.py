from trendbot.collectors.html_list import parse_list
from trendbot.collectors.numbers import parse_count
from trendbot.collectors.signals import parse_google_news, parse_google_trends


def test_parse_count():
    assert parse_count("1,234") == 1234
    assert parse_count("1.2만") == 12000
    assert parse_count("[12]") == 12
    assert parse_count("조회 3천") == 3000
    assert parse_count("5 - 0") == 5
    assert parse_count("") is None and parse_count(None) is None


def test_parse_list_generic():
    html = """<table><tr class="r"><td class="t"><a href="/p/1">첫 글</a><span class="c">[3]</span></td><td class="v">1.5만</td></tr>
    <tr class="r"><td class="t"><a href="/p/2">둘째 글</a></td><td class="v">900</td></tr>
    <tr class="r"><td class="t"></td></tr></table>"""
    src = {"id": "x", "url": "https://ex.com/best", "row": "tr.r",
           "fields": {"title": "td.t a", "link": "td.t a@href", "views": "td.v", "comments": "span.c"}}
    posts = parse_list(html, src)
    assert [p.title for p in posts] == ["첫 글", "둘째 글"]
    assert posts[0].url == "https://ex.com/p/1" and posts[0].views == 15000 and posts[0].comments == 3
    assert posts[1].rank == 2


def test_google_trends_rss():
    xml = """<rss xmlns:ht="https://trends.google.com/trending/rss"><channel><item><title>구름빵</title>
    <ht:approx_traffic>50,000+</ht:approx_traffic><ht:news_item><ht:news_item_title>품절 대란</ht:news_item_title>
    <ht:news_item_url>https://n.ex/1</ht:news_item_url></ht:news_item></item></channel></rss>"""
    s = parse_google_trends(xml)[0]
    assert s.title == "구름빵" and s.value == 50000 and s.extra["news"][0]["title"] == "품절 대란"


def test_google_news_rss():
    xml = """<rss><channel><item><title>제목입니다 - 한겨레</title><link>https://g.ex/a</link>
    <source url="x">한겨레</source></item></channel></rss>"""
    assert parse_google_news(xml)[0].title == "제목입니다"


def test_parse_original_generic_and_selectors():
    from trendbot.collectors.original import parse_original
    html = """<html><head><meta property="og:image" content="/og.jpg"></head><body><nav>메뉴 메뉴 메뉴</nav>
    <div class="view"><p>첫 줄 본문입니다. 충분히 긴 본문이 필요해서 내용을 조금 더 적습니다.</p><p>둘째 줄입니다. 계속해서 본문을 이어 갑니다.</p>
    <img src="/a.jpg"><img src="data:image/png;base64,xx"></div>
    <ul><li class="c"><span class="t">좋은 댓글</span><em>12</em></li><li class="c"><span class="t">최고 댓글</span><em>99</em></li></ul></body></html>"""
    o = parse_original(html, "https://ex.com/p/1", {"body": "div.view", "comment": "li.c", "comment_text": "span.t", "comment_likes": "em"})
    assert o["status"] == "ok" and "둘째 줄" in o["body"] and o["images"] == ["https://ex.com/a.jpg"]
    assert o["comments"][0] == {"text": "최고 댓글", "likes": 99}
    g = parse_original(html.replace("<head>", '<head><meta property="og:description" content="미리보기 문장">'), "https://ex.com/p/1")
    assert g["body"] == "미리보기 문장" and g["images"] == ["https://ex.com/og.jpg"] and g["comments"] == []
    login = parse_original("<html><body>로그인이 필요합니다</body></html>", "https://ex.com/x")
    assert login["status"] == "login"


import pathlib
import pytest

FIX = pathlib.Path(__file__).parent / "fixtures"


@pytest.mark.parametrize("sid", ["humoruniv", "ruliweb", "ppomppu_hot", "ppomppu_deal", "bobaedream"])
def test_real_site_fixtures(sid):
    """실제 화면 샘플로 목록·원문 읽기가 깨지지 않았는지 확인 (사이트 구조가 바뀌면 여기서 먼저 실패)."""
    from trendbot.collectors.original import parse_original
    from trendbot.config import load_config
    src = {s["id"]: s for s in load_config()["sources"]}[sid]
    posts = parse_list((FIX / f"{sid}.html").read_text(encoding="utf-8"), src)
    assert len(posts) >= 15
    assert sum(1 for p in posts if p.views) >= 15
    assert all("javascript" not in p.url for p in posts)
    o = parse_original((FIX / f"{sid}_post.html").read_text(encoding="utf-8"), posts[0].url, src.get("detail"))
    assert o["status"] == "ok"

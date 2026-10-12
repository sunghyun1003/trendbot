from trendbot.collectors.html_list import parse_list
from trendbot.collectors.numbers import parse_count
from trendbot.collectors.naver_cafe import articles_to_posts
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


def test_naver_cafe_json():
    payload = {"result": {"articleList": [{"item": {"articleId": 11, "subject": "인기글", "readCount": 2300,
                                                    "commentCount": 41, "likeItCount": 18}}]}}
    posts = articles_to_posts([payload], {"id": "dieselmania"}, 123)
    assert posts[0].views == 2300 and posts[0].likes == 18 and "cafes/123/articles/11" in posts[0].url


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

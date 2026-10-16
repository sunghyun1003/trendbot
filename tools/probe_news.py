"""임시: 구글 뉴스 검색 RSS가 robots.txt로 허용되는지, 결과가 오는지 (확인 후 삭제)."""
from trendbot.collectors.http import robots_allows
from trendbot.pipeline import context
for t in ["이준석 의원 조달 논란", "테슬라 신형 로드스터 시연", "에버랜드 카피바라 세쌍둥이"]:
    url = "https://news.google.com/rss/search?q=" + "+".join(context._keywords(t)) + "&hl=ko&gl=KR&ceid=KR:ko"
    print(t, "| robots:", robots_allows(url), "| results:", [n["title"][:40] for n in context.search_news(t)][:2])

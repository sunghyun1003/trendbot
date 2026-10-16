"""임시: 지금 쓰는 뉴스·트렌드 주소가 robots.txt로 허용되는지 (확인 후 삭제)."""
import httpx
from trendbot.collectors.http import robots_allows, USER_AGENT
for url in ["https://news.google.com/rss?hl=ko&gl=KR&ceid=KR:ko",
            "https://trends.google.com/trending/rss?geo=KR",
            "https://news.google.com/rss/search?q=test&hl=ko&gl=KR&ceid=KR:ko"]:
    print(url, "| robots:", robots_allows(url))
r = httpx.get("https://news.google.com/robots.txt", headers={"User-Agent": USER_AGENT})
print([l for l in r.text.splitlines() if l.lower().startswith(("user-agent", "allow", "disallow"))][:40])

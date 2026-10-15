"""임시 점검: 이슈링크의 인스티즈 목록 형식 + 인스티즈 원문 접속 가능 여부 (확인 후 삭제)."""
import re
import httpx
from bs4 import BeautifulSoup
from trendbot.collectors.http import USER_AGENT, robots_allows

c = httpx.Client(headers={"User-Agent": USER_AGENT, "Accept-Language": "ko-KR"}, timeout=20, follow_redirects=False)
for path in ["instiz/3/adj/_self/blank/blank/blank", "instiz/24/adj/_self/blank/blank/blank"]:
    url = f"https://www.issuelink.co.kr/community/listview/{path}"
    r = c.get(url)
    print("LIST", url, r.status_code, len(r.text))
    rows = BeautifulSoup(r.text, "html.parser").select("tr")
    n = 0
    for tr in rows:
        a = tr.select_one("span.title a")
        if not a:
            continue
        n += 1
        if n <= 4:
            print("  ROW", a.get("href"), "|", " ".join(a.get_text().split())[:40], "| hit:", (tr.select_one("span.hit") or a).get_text(strip=True)[:10])
    print("  rows with title:", n)
    if n:
        break
# 이슈링크 이동 주소가 실제로 어디로 가는지
a = BeautifulSoup(r.text, "html.parser").select_one("span.title a")
if a:
    go = httpx.URL(url).join(a["href"])
    r2 = c.get(go)
    print("GO", go, r2.status_code, r2.headers.get("location"))
    m = re.search(r"https?://[^\"' ]*instiz\.net[^\"' <]*", r2.text)
    print("  link in body:", m.group(0) if m else None)
    target = r2.headers.get("location") or (m.group(0) if m else None)
    if target:
        print("ROBOTS allows:", robots_allows(target))
        r3 = c.get(target)
        print("ORIGINAL", target, r3.status_code, len(r3.text), "challenge" if "captcha" in r3.text.lower() else "")
for u in ["https://www.instiz.net/pt?srt=3&srd=1", "https://www.instiz.net/robots.txt"]:
    r4 = c.get(u)
    print("DIRECT", u, r4.status_code, r4.text[:300].replace("\n", " ") if "robots" in u else "")

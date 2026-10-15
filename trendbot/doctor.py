"""`python -m trendbot doctor` — 키·접속 상태를 한 번에 점검하고 고칠 방법을 알려 줍니다 (개발·수리용).

평소에는 사이트 '상태' 화면의 키 ✓/✗ 로 충분합니다."""

from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass

import httpx

from trendbot.config import DATA_DIR


@dataclass
class Check:
    name: str
    ok: bool | None  # None = 선택 항목이 비어 있음(경고만)
    detail: str = ""
    fix: str = ""


KEY_RULES = {  # 모두 GitHub 저장소 Settings → Secrets and variables → Actions 에 넣음
    "ANTHROPIC_API_KEY": (r"^sk-ant-[\w-]{20,}$", True, "keys-guide 1번: console.anthropic.com → API Keys"),
    "CLOUDFLARE_ACCOUNT_ID": (r"^[0-9a-f]{32}$", True, "keys-guide 2번: Cloudflare 대시보드의 Account ID"),
    "CLOUDFLARE_API_TOKEN": (r"^[\w-]{30,}$", True, "keys-guide 3번: My Profile → API Tokens (권한 4가지)"),
    "ALLOWED_EMAILS": (r"^[^@\s,]+@[^@\s,]+(\s*,\s*[^@\s,]+@[^@\s,]+)*$", True, "keys-guide 5번: 볼 사람 이메일을 쉼표로"),
    "DASHBOARD_TOKEN": (r"^(github_pat_|ghp_)\w{20,}$", True, "keys-guide 6번: GitHub → Fine-grained token"),
    "YOUTUBE_API_KEY": (r"^AIza[\w-]{30,}$", False, "keys-guide 7번: Google Cloud → 사용자 인증 정보 → API 키"),
}


def check_keys(env: dict | None = None) -> list[Check]:
    env = env if env is not None else os.environ
    out = []
    for key, (pattern, required, where) in KEY_RULES.items():
        val = (env.get(key) or "").strip()
        if not val:
            out.append(Check(key, False if required else None, "비어 있음", where))
        elif not re.match(pattern, val):
            out.append(Check(key, False, "형식이 이상함 (앞뒤 공백·따옴표·잘림 확인)", where))
        else:
            out.append(Check(key, True, f"{val[:6]}…"))
    return out


def check_live_keys(env=os.environ) -> list[Check]:
    out = []
    if env.get("ANTHROPIC_API_KEY"):
        try:
            import anthropic
            anthropic.Anthropic().models.retrieve("claude-sonnet-5-5")
            out.append(Check("Anthropic 연결", True, "Sonnet 5.5 사용 가능"))
        except Exception as e:
            out.append(Check("Anthropic 연결", False, e.__class__.__name__,
                             "키가 맞는지, 크레딧이 충전돼 있는지 console.anthropic.com에서 확인"))
    if env.get("YOUTUBE_API_KEY"):
        try:
            r = httpx.get("https://www.googleapis.com/youtube/v3/videos",
                          params={"part": "id", "chart": "mostPopular", "regionCode": "KR", "maxResults": 1,
                                  "key": env["YOUTUBE_API_KEY"]}, timeout=15)
            out.append(Check("YouTube 연결", r.status_code == 200, f"응답 {r.status_code}",
                             "" if r.status_code == 200 else "YouTube Data API v3를 '사용'으로 켰는지, 키 제한이 맞는지 확인"))
        except httpx.HTTPError as e:
            out.append(Check("YouTube 연결", False, e.__class__.__name__, "인터넷 연결 확인"))
    if env.get("CLOUDFLARE_API_TOKEN"):
        try:
            r = httpx.get("https://api.cloudflare.com/client/v4/user/tokens/verify",
                          headers={"Authorization": f"Bearer {env['CLOUDFLARE_API_TOKEN']}"}, timeout=15)
            ok = r.status_code == 200 and r.json().get("success")
            out.append(Check("Cloudflare 토큰", bool(ok), "유효" if ok else f"응답 {r.status_code}",
                             "" if ok else "토큰을 새로 만들고 Pages: Edit 권한을 줬는지 확인"))
        except httpx.HTTPError as e:
            out.append(Check("Cloudflare 토큰", False, e.__class__.__name__, "인터넷 연결 확인"))
    return out


def check_site_locked(url: str) -> Check:
    """로그인 없이 열었을 때 막혀야 정상 (302/401/403)."""
    try:
        r = httpx.get(url, follow_redirects=False, timeout=15)
    except httpx.HTTPError as e:
        return Check(f"잠금 {url}", False, e.__class__.__name__, "주소 확인")
    locked = r.status_code in (302, 401, 403) or "cloudflareaccess.com" in r.headers.get("location", "")
    return Check(f"잠금 {url}", locked, f"응답 {r.status_code}",
                 "" if locked else "누구나 볼 수 있는 상태! keys-guide 3-4대로 Access 잠금을 먼저 거세요")


def check_tools() -> list[Check]:
    out = [Check("Node.js(npx)", shutil.which("npx") is not None, "",
                 "https://nodejs.org 에서 LTS 설치 (사이트 올리기에 필요)")]
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            exe = os.environ.get("TRENDBOT_CHROMIUM")
            b = pw.chromium.launch(executable_path=exe) if exe else pw.chromium.launch()
            b.close()
        out.append(Check("브라우저(Playwright)", True, "본문 캡처용"))
    except Exception as e:
        out.append(Check("브라우저(Playwright)", False, e.__class__.__name__, "python -m playwright install chromium"))
    return out


def check_sources(cfg: dict) -> list[Check]:
    from trendbot.collectors import html_list
    out = []
    for src in cfg["sources"]:
        if not src.get("enabled", True):
            continue
        try:
            n = len(html_list.collect(src))
            out.append(Check(src["name"], n > 0, f"{n}줄", "" if n else "화면 구조가 바뀜 → Claude Code에 '고장 수리'"))
        except Exception as e:
            out.append(Check(src["name"], False, str(e)[:60], "차단이면 우회하지 않고 꺼 둠(sources.yaml enabled: false)"))
    return out


def render(checks: list[Check]) -> str:
    lines = []
    for c in checks:
        mark = "✓" if c.ok else ("–" if c.ok is None else "✗")
        line = f" {mark} {c.name:<28} {c.detail}"
        if c.ok is not True and c.fix:
            line += f"\n     → {c.fix}"
        lines.append(line)
    return "\n".join(lines)


def run(cfg: dict, quick: bool = False) -> int:
    sections = [("키", check_keys()), ("연결", check_live_keys()), ("도구", check_tools())]
    if not quick:
        sections.append(("수집 소스", check_sources(cfg)))
    failed = 0
    for title, checks in sections:
        print(f"\n[{title}]\n{render(checks) if checks else ' – 확인할 키가 아직 없어 건너뜀'}")
        failed += sum(1 for c in checks if c.ok is False)
    print("\n모두 정상입니다." if not failed else f"\n고칠 것 {failed}개. 위의 → 안내를 따라 주세요.")
    return 1 if failed else 0

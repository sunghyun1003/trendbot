"""'처음 설정' (GitHub 웹에서 버튼 한 번): Cloudflare에 필요한 것을 모두 자동으로 만듭니다.

이미 있으면 건너뛰거나 최신 값으로 맞추므로, 몇 번을 다시 눌러도 안전합니다.
1. Pages 프로젝트(사이트)            4. 팀원 로그인 잠금(Access) + 이메일 인증번호 로그인
2. KV 저장소(팀원 피드백)            5. (내 도메인이 있으면) 도메인 연결
3-1. 정시 실행기(Cloudflare Worker): 06:30 발행·2시간마다 수집을 정확한 시각에 시작
3. 사이트 설정값(로그인 검증값, 대시보드용 GitHub 토큰)

필요한 GitHub 비밀값: CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_API_TOKEN, ALLOWED_EMAILS, (DASHBOARD_TOKEN, SITE_DOMAIN)
SITE_DOMAIN(내 도메인)을 넣으면 사이트에 그 주소를 붙이고, 로그인 잠금도 같은 주소에 함께 겁니다.
"""

from __future__ import annotations

import json
import os
import re

from trendbot.cloudflare import PROJECT, Client, CloudflareError
from trendbot.config import ROOT

APP_NAME = "ㄷㅅㅂㄱ"
OLD_AGENT_APP_NAME = "ㄷㅅㅂㄱ 집 PC 도우미 창구"  # 예전 버전이 만든 잠금 예외. 있으면 지움


SCHEDULER = "dsbg-scheduler"
PUBLISH_CRON = "30 21 * * *"      # 06:30 한국 시각 (UTC 기준으로 적음)
COLLECT_CRON = "7 */2 * * *"      # 2시간마다 (매시 7분)


class SetupError(Exception):
    pass


def emails() -> list[str]:
    raw = os.environ.get("ALLOWED_EMAILS", "")
    found = [e.strip().lower() for e in re.split(r"[,\s;]+", raw) if e.strip()]
    bad = [e for e in found if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", e)]
    if bad or not found:
        raise SetupError("ALLOWED_EMAILS 비밀값에 사이트를 볼 이메일을 쉼표로 적어 주세요"
                         + (f" (이상한 값: {', '.join(bad)})" if bad else ""))
    return found


def ensure_project(cf: Client) -> str:
    try:
        p = cf.call("GET", f"/pages/projects/{PROJECT}")
    except CloudflareError as e:
        if "404" not in str(e):
            raise
        p = cf.call("POST", "/pages/projects", json={"name": PROJECT, "production_branch": "main"})
    return p["subdomain"]


def ensure_login_method(cf: Client) -> None:
    """이메일로 받은 6자리 번호로 로그인 (별도 계정 불필요)."""
    idps = cf.call("GET", "/access/identity_providers") or []
    if not any(i.get("type") == "onetimepin" for i in idps):
        cf.call("POST", "/access/identity_providers", json={"name": "이메일 인증번호", "type": "onetimepin", "config": {}})


def _upsert_app(cf: Client, apps: list[dict], body: dict) -> dict:
    cur = next((a for a in apps if a.get("name") == body["name"]), None)
    if cur:
        return cf.call("PUT", f"/access/apps/{cur['id']}", json={**cur, **body})
    return cf.call("POST", "/access/apps", json=body)


def site_domain() -> str | None:
    raw = (os.environ.get("SITE_DOMAIN") or "").strip().lower()
    raw = re.sub(r"^https?://", "", raw).strip("/")
    if not raw:
        return None
    if not re.fullmatch(r"[a-z0-9-]+(\.[a-z0-9-]+)+", raw):
        raise SetupError(f"SITE_DOMAIN 형식이 이상합니다: {raw} (예: dsbg.mydomain.com)")
    return raw


def ensure_custom_domain(cf: Client, domain: str) -> str:
    """Pages에 내 도메인 연결. 상태 문자열을 돌려줌 (active / pending 등)."""
    have = cf.call("GET", f"/pages/projects/{PROJECT}/domains") or []
    cur = next((d for d in have if d.get("name") == domain), None)
    if not cur:
        cur = cf.call("POST", f"/pages/projects/{PROJECT}/domains", json={"name": domain})
    return cur.get("status") or "pending"


def ensure_access(cf: Client, host: str, allowed: list[str], domain: str | None = None) -> tuple[str, str]:
    try:
        org = cf.call("GET", "/access/organizations")
    except CloudflareError as e:
        raise SetupError("Cloudflare Zero Trust를 아직 시작하지 않았습니다. keys-guide의 'Zero Trust 시작'을 먼저 해 주세요") from e
    team = org["auth_domain"]
    ensure_login_method(cf)
    apps = cf.call("GET", "/access/apps") or []
    app = _upsert_app(cf, apps, {
        "name": APP_NAME, "type": "self_hosted", "domain": host,
        "self_hosted_domains": [host, f"*.{host}"] + ([domain] if domain else []),  # 미리보기·내 도메인까지 잠금
        "session_duration": "720h", "app_launcher_visible": False,
        "policies": [{"name": "팀원", "decision": "allow", "precedence": 1,
                      "include": [{"email": {"email": e}} for e in allowed]}],
    })
    for a in apps:  # 집 PC 도우미를 없앴으므로 예전 잠금 예외(/api/agent)를 삭제
        if a.get("name") == OLD_AGENT_APP_NAME:
            cf.call("DELETE", f"/access/apps/{a['id']}")
    return team, app["aud"]


def ensure_scheduler(cf: Client) -> str:
    """정시 실행기(Worker)를 올리고 시각을 등록. 결과를 한국어 한 줄로 (실패해도 설정 전체는 계속)."""
    token = os.environ.get("DASHBOARD_TOKEN")
    if not token:
        return "정시 실행기: DASHBOARD_TOKEN이 없어 건너뜀 (GitHub 자체 예약으로만 실행, 늦어질 수 있음)"
    meta = {"main_module": "scheduler.js", "compatibility_date": "2026-01-01", "bindings": [
        {"type": "secret_text", "name": "GITHUB_TOKEN", "text": token},
        {"type": "plain_text", "name": "GITHUB_REPO", "text": os.environ.get("GITHUB_REPOSITORY", "")},
        {"type": "plain_text", "name": "GITHUB_BRANCH", "text": os.environ.get("GITHUB_REF_NAME", "main")},
        {"type": "plain_text", "name": "PUBLISH_CRON", "text": PUBLISH_CRON},
    ]}
    code = (ROOT / "worker" / "scheduler.js").read_bytes()
    try:
        cf.call("PUT", f"/workers/scripts/{SCHEDULER}", files={
            "metadata": (None, json.dumps(meta), "application/json"),
            "scheduler.js": ("scheduler.js", code, "application/javascript+module")})
        cf.call("PUT", f"/workers/scripts/{SCHEDULER}/schedules", json=[{"cron": PUBLISH_CRON}, {"cron": COLLECT_CRON}])
    except CloudflareError as e:
        if " 403 " in str(e) or "Authentication" in str(e) or "permission" in str(e).lower():
            return ("정시 실행기: ✗ Cloudflare 토큰에 'Workers Scripts: Edit' 권한이 없어 설치하지 못함 "
                    "(keys-guide 3번에서 권한 추가 후 처음 설정 다시)")
        return f"정시 실행기: ✗ 설치 실패 ({str(e)[:120]})"
    return "정시 실행기: 매일 06:30 발행, 2시간마다 수집"


def configure_project(cf: Client, kv_id: str, team: str, aud: str) -> None:
    env = {
        "ACCESS_TEAM_DOMAIN": {"type": "plain_text", "value": team},
        "ACCESS_AUD": {"type": "plain_text", "value": aud},
        "GITHUB_REPO": {"type": "plain_text", "value": os.environ.get("GITHUB_REPOSITORY", "")},
        "GITHUB_BRANCH": {"type": "plain_text", "value": os.environ.get("GITHUB_REF_NAME", "main")},
    }
    if os.environ.get("DASHBOARD_TOKEN"):
        env["GITHUB_TOKEN"] = {"type": "secret_text", "value": os.environ["DASHBOARD_TOKEN"]}
    conf = {"kv_namespaces": {"FEEDBACK": {"namespace_id": kv_id}}, "env_vars": env}
    cf.call("PATCH", f"/pages/projects/{PROJECT}", json={"deployment_configs": {"production": conf, "preview": conf}})


def run(cf: Client | None = None) -> list[str]:
    """해낸 일을 한국어 줄로 돌려줌. 막히면 SetupError(고칠 방법 포함)."""
    for k in ("CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_API_TOKEN"):
        if not os.environ.get(k):
            raise SetupError(f"{k} 비밀값이 비어 있습니다 (keys-guide 참고)")
    allowed = emails()
    domain = site_domain()
    cf = cf or Client()
    done = []
    try:
        host = ensure_project(cf)
        done.append(f"사이트 주소: https://{host}")
        kv_id = cf.kv_namespace(create=True)
        done.append("저장소(KV) 준비")
        team, aud = ensure_access(cf, host, allowed, domain)  # 잠금을 먼저 건 뒤에 도메인을 붙임
        done.append(f"팀원 로그인 잠금: {len(allowed)}명 ({', '.join(allowed)})")
        if domain:
            status = ensure_custom_domain(cf, domain)
            done.append(f"내 도메인: https://{domain} ({'연결됨' if status == 'active' else '연결 중, 몇 분~몇 시간 뒤 열림'})")
        configure_project(cf, kv_id, team, aud)
        done.append(ensure_scheduler(cf))
        done.append("사이트 설정값 연결" + ("" if os.environ.get("DASHBOARD_TOKEN") else
                                      " (DASHBOARD_TOKEN이 없어 대시보드 버튼은 꺼진 상태)"))
    except CloudflareError as e:
        msg = str(e)
        if " 403 " in msg or "Authentication" in msg:
            raise SetupError(f"Cloudflare 토큰 권한이 부족합니다. keys-guide의 토큰 권한 4가지를 확인해 주세요. ({msg[:120]})") from e
        raise SetupError(f"Cloudflare 응답 오류: {msg[:200]}") from e
    return done


def main() -> int:
    try:
        lines = run()
    except SetupError as e:
        print(f"## ✗ 처음 설정이 멈췄습니다\n\n{e}")
        return 1
    print("## ✓ 처음 설정 완료\n\n" + "\n".join(f"- {l}" for l in lines)
          + "\n\n이어서 첫 발행이 자동으로 진행됩니다. 끝나면 위 사이트 주소로 들어가세요.")
    return 0

"""ㄷㅅㅂㄱ 집 PC 도우미 (윈도우 작업 스케줄러가 30분마다 조용히 실행).

하는 일 (네이버 카페 전용: 디젤매니아·파우더룸·스사사 등, 나머지 수집은 GitHub 서버가 함)
- 매번: 사이트에 '살아 있음'과 네이버 로그인 상태를 알림, 새 버전 코드가 있으면 받아 둠
- 하루 2번(10시간 간격) 또는 대시보드에서 '디젤매니아 지금 수집'을 눌렀을 때:
  인기글 목록 + 상위 글 원문·사진을 읽어 사이트로 보냄
- 'login' 으로 실행하면(바탕화면 아이콘) 네이버 로그인 창을 열고, 닫으면 바로 한 번 수집

자동 로그인은 하지 않습니다. 사용자가 연 창에서 직접 로그인한 상태(쿠키)만 다시 씁니다.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import sys
import traceback
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

APP = Path(__file__).resolve().parent            # %LOCALAPPDATA%\dsbg\app
BASE = APP.parent                                # %LOCALAPPDATA%\dsbg
CONF = BASE / "config.json"                      # {"token": ..., "site": ...} (설치 파일이 만듦)
STATE = BASE / "state.json"
LOG = BASE / "helper.log"
TOP_ORIGINALS = 5
COLLECT_EVERY = timedelta(hours=10)
ACTIVE_HOURS = range(5, 24)                      # 새벽에는 수집하지 않음

os.environ.setdefault("TRENDBOT_BROWSER", "msedge")  # 윈도우 기본 Edge 사용 (따로 설치 없음)
sys.path.insert(0, str(APP))


def log(msg: str) -> None:
    line = f"{datetime.now():%Y-%m-%d %H:%M} {msg}\n"
    try:
        if LOG.exists() and LOG.stat().st_size > 1_000_000:
            LOG.write_text("", encoding="utf-8")
        with LOG.open("a", encoding="utf-8") as f:
            f.write(line)
    except OSError:
        pass


def load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


class Site:
    def __init__(self, conf: dict):
        import httpx
        self.base = conf["site"].rstrip("/") + "/api/agent"
        self.http = httpx.Client(timeout=60, headers={"X-Agent-Token": conf["token"]})

    def get(self, what: str):
        r = self.http.get(self.base, params={"get": what})
        r.raise_for_status()
        return r

    def put(self, what: str, **kw):
        params = {"put": what, **kw.pop("params", {})}
        r = self.http.post(self.base, params=params, **kw)
        r.raise_for_status()


def update_code(site: Site) -> str:
    """새 코드가 있으면 app 폴더에 풀어 둠 (다음 실행부터 적용). 현재 버전(해시 앞자리)을 돌려줌."""
    data = site.get("code").content
    ver = hashlib.sha1(data).hexdigest()[:8]
    if ver != load(STATE).get("version"):
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            z.extractall(APP)
        save_state(version=ver)
        log(f"코드 업데이트 {ver}")
    return ver


def save_state(**kw) -> None:
    s = load(STATE)
    s.update(kw)
    STATE.write_text(json.dumps(s), encoding="utf-8")


def collect_one(site: Site, src: dict) -> tuple[str, str]:
    """카페 한 곳 수집 → 사이트로 보냄. (네이버 상태, 메시지)"""
    from trendbot.collectors import media
    from trendbot.collectors.naver_cafe import LoginRequired, collect as cafe_collect, fetch_originals
    from trendbot.models import now_iso

    at = now_iso()
    try:
        posts = cafe_collect(src)
    except LoginRequired as e:
        site.put("batch", json={"source_id": src["id"], "at": at, "ok": False, "message": str(e)})
        return "login", f"{src['name']}: {e}"
    if not posts:
        site.put("batch", json={"source_id": src["id"], "at": at, "ok": False, "message": "인기글을 하나도 읽지 못함"})
        return "ok", f"{src['name']}: 인기글 0건"
    top = sorted(posts, key=lambda p: p.rank)[:TOP_ORIGINALS]
    originals = fetch_originals([p.url for p in top])
    day = at[:10]
    for p in top:
        o = originals.get(p.url) or {}
        if o.get("status") != "ok":
            continue
        o["saved"] = media.download_images(o.get("images", [])[:media.MAX_IMAGES], p.url, day)
        for s in o["saved"]:
            f = media.DATA_DIR / s["file"]
            site.put("media", params={"name": s["file"].removeprefix("media/")}, content=f.read_bytes())
    site.put("batch", json={"source_id": src["id"], "at": at, "ok": True,
                            "posts": [p.to_dict() for p in posts], "originals": originals})
    return "ok", f"{src['name']}: 인기글 {len(posts)}건, 원문 {sum(1 for o in originals.values() if o.get('status') == 'ok')}개"


def collect(site: Site) -> tuple[str, str]:
    """켜져 있는 네이버 카페를 차례로 수집. 한 곳이 실패해도 나머지는 계속.
    네이버 상태는 모든 카페가 로그인 문제일 때만 'login' (한 곳만 막히면 그 카페 가입 문제)."""
    from trendbot.collectors import media
    from trendbot.config import load_config

    cafes = [s for s in load_config()["sources"] if s.get("kind") == "naver_cafe" and s.get("enabled", True)]
    results = []
    for src in cafes:
        try:
            results.append(collect_one(site, src))
        except Exception as e:  # 이 카페만 건너뜀
            results.append(("error", f"{src['name']}: {e.__class__.__name__}"))
    media.prune(7)  # 집 PC에는 일주일만 남김 (사이트 쪽 보관은 GitHub 서버가 함)
    states = [r[0] for r in results]
    naver = "login" if states and all(s == "login" for s in states) else "ok"
    return naver, " / ".join(r[1] for r in results)[:300]


def run(force_collect: bool = False) -> int:
    conf = load(CONF)
    if not conf.get("token"):
        log("설정 파일이 없습니다. 대시보드에서 설치 파일을 다시 받아 실행하세요.")
        return 1
    site = Site(conf)
    state = load(STATE)
    naver, msg = state.get("naver", ""), ""
    try:
        ver = update_code(site)
        cmd = site.get("cmd").json().get("cmd")
        last = state.get("last_collect")
        due = not last or datetime.now() - datetime.fromisoformat(last) >= COLLECT_EVERY
        if force_collect or cmd == "collect" or (due and datetime.now().hour in ACTIVE_HOURS):
            naver, msg = collect(site)
            save_state(last_collect=datetime.now().isoformat(timespec="minutes"), naver=naver)
            log(f"수집: {msg}")
        site.put("status", json={"naver": naver, "message": msg, "version": ver, "last_collect": load(STATE).get("last_collect")})
        return 0
    except Exception as e:  # 다음 실행에서 다시 시도
        log(f"오류: {e.__class__.__name__}: {e}\n{traceback.format_exc(limit=3)}")
        try:
            site.put("status", json={"naver": naver, "message": f"오류: {e.__class__.__name__}"[:200]})
        except Exception:
            pass
        return 1


def login() -> int:
    from trendbot.collectors.naver_cafe import open_login_window
    open_login_window()  # 사용자가 직접 로그인하고 창을 닫을 때까지 기다림
    save_state(naver="")
    return run(force_collect=True)


if __name__ == "__main__":
    sys.exit(login() if sys.argv[1:] == ["login"] else run())

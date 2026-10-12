"""명령어 모음. 집 PC에서 `python -m trendbot <명령>`으로 실행합니다.

  snapshot      게시판·검색·영상 신호를 한 번 수집 (하루 5회 예약 실행)
  daily         오늘의 판을 만들고 사이트를 생성·배포 (매일 07:00 예약 실행)
  probe         처음 설치 때 1회: 사이트별 접속·차단·선택자 점검, 화면 샘플 저장
  naver-login   네이버 로그인 창 열기 (직접 로그인)
  build-site    저장된 판으로 사이트만 다시 생성
  deploy        public/ 폴더를 Cloudflare Pages에 올리기
  sample        견본 데이터로 사이트 미리보기 생성
  pull-feedback 팀원 피드백(유지/제외/놓친 것) 가져오기 (daily에서 자동 실행)
  doctor        설치·키·접속 상태를 한 번에 점검
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

from trendbot import storage
from trendbot.collectors import html_list, signals
from trendbot.collectors.http import Blocked
from trendbot.config import ROOT, ConfigError, load_config


def _load_env() -> None:
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def cmd_snapshot(cfg: dict, include_naver: bool) -> int:
    db = storage.connect()
    failures = 0
    for src in cfg["sources"]:
        if not src.get("enabled", True):
            continue
        kind = src.get("kind", "html_list")
        if kind == "naver_cafe" and not include_naver:
            continue
        try:
            if kind == "naver_cafe":
                from trendbot.collectors import naver_cafe
                posts = naver_cafe.collect(src)
            else:
                posts = html_list.collect(src)
            if not posts:
                raise ValueError("목록을 하나도 읽지 못함 (화면 구조가 바뀌었을 수 있음)")
            storage.save_posts(db, posts)
            storage.log_run(db, src["id"], True, len(posts))
            print(f"  ✓ {src['name']}: {len(posts)}건")
        except Exception as e:  # 한 사이트가 고장 나도 나머지는 계속
            failures += 1
            storage.log_run(db, src["id"], False, 0, str(e)[:200])
            print(f"  ✗ {src['name']}: {e}")
    for name, fn in (("google_trends", signals.google_trends), ("google_news", signals.google_news),
                     ("youtube", signals.youtube_discovery)):
        if not cfg["signals"].get(name, {}).get("enabled"):
            continue
        try:
            sigs = fn(cfg)
            storage.save_signals(db, sigs)
            storage.log_run(db, name, True, len(sigs))
            print(f"  ✓ {name}: {len(sigs)}건")
        except Exception as e:
            failures += 1
            storage.log_run(db, name, False, 0, str(e)[:200])
            print(f"  ✗ {name}: {e}")
    storage.prune(db)
    return 1 if failures and failures >= len(cfg["sources"]) else 0


def _health_rows(cfg: dict) -> list[dict]:
    from datetime import datetime, timedelta
    db = storage.connect()
    h = storage.source_health(db, (datetime.now().astimezone() - timedelta(hours=26)).isoformat())
    return [{"name": s["name"], "enabled": s.get("enabled", True), "verified": s.get("verified", False),
             "ok": h.get(s["id"], {}).get("ok", False), "message": h.get(s["id"], {}).get("message") or "수집 기록 없음"}
            for s in cfg["sources"]]


def cmd_build_site(cfg: dict) -> None:
    from trendbot.site.build import build
    out = build(storage.load_editions(storage.connect()), _health_rows(cfg))
    print(f"사이트 생성: {out}")


def cmd_daily(cfg: dict, use_ai: bool, deploy: bool) -> None:
    from trendbot.pipeline.edition import build_edition
    from trendbot import feedback
    from trendbot.collectors import media
    db = storage.connect()
    print(feedback.pull(db))
    media.prune()
    edition = build_edition(db, cfg, use_ai=use_ai)
    storage.save_edition(db, edition)
    print(f"오늘의 필수 {len(edition['cards'])}건, 채널 1위 {sum(1 for c in edition['champions'] if c['post'])}줄")
    cmd_build_site(cfg)
    if deploy:
        cmd_deploy()


def cmd_deploy() -> None:
    """public/ 폴더를 Cloudflare Pages에 올림. 처음이면 프로젝트부터 만듦."""
    project = os.environ.get("CF_PAGES_PROJECT", "trendbot")
    win = sys.platform == "win32"
    wrangler = ["npx", "--yes", "wrangler@3", "pages"]
    # 이미 있으면 실패해도 괜찮음
    subprocess.run(wrangler + ["project", "create", project, "--production-branch", "main"], cwd=ROOT, shell=win,
                   capture_output=True)
    subprocess.run(wrangler + ["deploy", str(ROOT / "public"), "--project-name", project, "--branch", "main",
                               "--commit-dirty=true"], check=True, cwd=ROOT, shell=win)


def main(argv: list[str] | None = None) -> int:
    _load_env()
    ap = argparse.ArgumentParser(prog="trendbot", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("snapshot")
    s.add_argument("--naver", action="store_true", help="네이버 카페도 수집 (하루 1~2회만)")
    d = sub.add_parser("daily")
    d.add_argument("--no-ai", action="store_true")
    d.add_argument("--no-deploy", action="store_true")
    sub.add_parser("probe")
    sub.add_parser("naver-login")
    sub.add_parser("build-site")
    sub.add_parser("deploy")
    sub.add_parser("sample")
    sub.add_parser("pull-feedback")
    dr = sub.add_parser("doctor")
    dr.add_argument("--quick", action="store_true", help="사이트 접속 점검 생략")
    args = ap.parse_args(argv)

    try:
        cfg = load_config()
    except ConfigError as e:
        print(f"[설정 오류] {e}")
        return 2

    if args.cmd == "snapshot":
        return cmd_snapshot(cfg, args.naver)
    if args.cmd == "daily":
        cmd_daily(cfg, use_ai=not args.no_ai, deploy=not args.no_deploy)
    elif args.cmd == "probe":
        from tools.probe import run
        run(cfg)
    elif args.cmd == "naver-login":
        from trendbot.collectors.naver_cafe import open_login_window
        open_login_window()
    elif args.cmd == "build-site":
        cmd_build_site(cfg)
    elif args.cmd == "pull-feedback":
        from trendbot import feedback
        print(feedback.pull(storage.connect()))
    elif args.cmd == "doctor":
        from trendbot.doctor import run as doctor_run
        return doctor_run(cfg, quick=args.quick)
    elif args.cmd == "deploy":
        cmd_deploy()
    elif args.cmd == "sample":
        from trendbot.site.build import build
        from trendbot.sample import sample_editions
        out = build(sample_editions(), [
            {"name": s["name"], "enabled": s.get("enabled", True), "verified": s.get("verified", False),
             "ok": s.get("enabled", True), "message": ""} for s in cfg["sources"]])
        print(f"견본 사이트 생성: {out / 'index.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

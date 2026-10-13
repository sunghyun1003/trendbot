"""명령어 모음. GitHub 서버(.github/workflows/run.yml)가 자동으로 실행합니다. 사용자가 직접 칠 일은 없습니다.

  snapshot      게시판·검색·영상·SNS 신호를 한 번 수집 (2시간마다 예약 실행)
  daily         오늘의 판을 만들고 사이트를 생성·배포 (매일 아침 예약 실행)
  probe         처음 설치 때 1회: 사이트별 접속·차단·선택자 점검, 화면 샘플 저장
  build-site    저장된 판으로 사이트만 다시 생성
  deploy        public/ 폴더를 Cloudflare Pages에 올리기
  sample        견본 데이터로 사이트 미리보기 생성
  pull-feedback 팀원 피드백(유지/제외/놓친 것) 가져오기 (daily에서 자동 실행)
  doctor        설치·키·접속 상태를 한 번에 점검
  report        수집 품질 리포트 (사이트별 성공률, 원문·사진·댓글)
  cloud-setup   처음 설정: Cloudflare 사이트·저장소·로그인 잠금·정시 실행기 자동 생성
  published-today 오늘 판이 이미 있는지 (예비 발행 중복 방지)
"""

from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path
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


def cmd_snapshot(cfg: dict) -> int:
    db = storage.connect()
    failures = 0
    for src in cfg["sources"]:
        if not src.get("enabled", True):
            continue
        try:
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
                     ("youtube", signals.youtube_discovery), ("youtube_chart", signals.youtube_chart),
                     ("x_trends", signals.x_trends), ("ent_news", signals.ent_news)):
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
    from trendbot.collectors import instagram
    if instagram.configured() and instagram.watchlist():
        try:
            sigs, failed = instagram.collect(cfg)
            storage.save_signals(db, sigs)
            storage.log_run(db, "instagram", True, len(sigs), f"읽지 못한 계정: {', '.join(failed)}" if failed else "")
            print(f"  ✓ instagram: 튄 게시물 {len(sigs)}건" + (f" (읽지 못한 계정 {len(failed)}개)" if failed else ""))
        except Exception as e:
            storage.log_run(db, "instagram", False, 0, str(e)[:200])
            print(f"  ✗ instagram: {e}")
    storage.prune(db)
    return 1 if failures and failures >= len(cfg["sources"]) else 0


SIGNAL_NAMES = {"google_trends": "구글 트렌드", "google_news": "구글 뉴스", "ent_news": "다음 연예 많이 본 뉴스",
                "x_trends": "X 실시간 트렌드", "youtube": "유튜브 급상승", "youtube_chart": "유튜브 인기 차트",
                "instagram": "인스타 감시 계정"}


def _health_rows(cfg: dict) -> list[dict]:
    """상태 탭용: 커뮤니티(켜기·끄기 가능)와 검색·뉴스·SNS 신호의 최근 수집 결과."""
    from datetime import datetime, timedelta
    from trendbot.collectors import instagram
    db = storage.connect()
    h = storage.source_health(db, (datetime.now().astimezone() - timedelta(hours=26)).isoformat())

    def row(sid, name, group, enabled):
        r = h.get(sid, {})
        return {"id": sid, "name": name, "group": group, "enabled": enabled, "ok": r.get("ok", False),
                "rows": r.get("rows"), "at": r.get("at"), "message": r.get("message") or "수집 기록 없음"}

    rows = [row(s["id"], s["name"], "community", s.get("enabled", True)) for s in cfg["sources"]]
    for sid, sc in cfg["signals"].items():
        if sc.get("enabled"):
            rows.append(row(sid, SIGNAL_NAMES.get(sid, sid), "signal", True))
    if instagram.configured():
        rows.append(row("instagram", SIGNAL_NAMES["instagram"], "signal", True))
    return rows


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
    try:  # 외부 기준(이슈링크) 대조: 실패해도 발행은 계속
        from trendbot import benchmark
        edition["benchmark"] = benchmark.run(db, edition)
        if edition["benchmark"]:
            b = edition["benchmark"]
            print(f"외부 기준 대조: 이슈링크 상위 {b['total']}개 중 수집 {b['collected']}, 판에 오름 {b['in_edition']}")
    except Exception as e:
        print(f"외부 기준 대조 실패: {e}")
    storage.save_edition(db, edition)
    print(f"오늘의 필수 {len(edition['cards'])}건, 채널 1위 {sum(1 for c in edition['champions'] if c['post'])}줄")
    cmd_build_site(cfg)
    if deploy:
        cmd_deploy()


def cmd_deploy() -> None:
    """public/ 폴더를 Cloudflare Pages에 올림.
    올리기 전에 항상 '처음 설정'과 같은 점검(사이트·팀원 로그인 잠금)을 먼저 해서, 잠기지 않은 주소에는 절대 올리지 않음."""
    from trendbot import cloud_setup
    from trendbot.cloudflare import PROJECT as project
    try:
        for line in cloud_setup.run():
            print(f"설정 점검: {line}")
    except cloud_setup.SetupError as e:
        raise SystemExit(f"사이트 잠금을 확인하지 못해 올리지 않음: {e}")
    win = sys.platform == "win32"
    wrangler = ["npx", "--yes", "wrangler@3", "pages"]
    # 서버 기능(관리 버튼·피드백)은 실행 위치의 functions/ 폴더에서 읽히므로, 임시 폴더에 functions/를 두고 그 안에서 올림
    import shutil
    import tempfile
    with tempfile.TemporaryDirectory() as work:
        shutil.copytree(ROOT / "site_functions", Path(work) / "functions")
        subprocess.run(wrangler + ["deploy", str(ROOT / "public"), "--project-name", project, "--branch", "main",
                                   "--commit-dirty=true"], check=True, cwd=work, shell=win)


def main(argv: list[str] | None = None) -> int:
    _load_env()
    ap = argparse.ArgumentParser(prog="trendbot", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("snapshot")
    d = sub.add_parser("daily")
    d.add_argument("--no-ai", action="store_true")
    d.add_argument("--no-deploy", action="store_true")
    sub.add_parser("probe")
    sub.add_parser("build-site")
    sub.add_parser("deploy")
    sub.add_parser("sample")
    sub.add_parser("pull-feedback")
    sub.add_parser("report")
    sub.add_parser("cloud-setup")
    sub.add_parser("published-today")
    dr = sub.add_parser("doctor")
    dr.add_argument("--quick", action="store_true", help="사이트 접속 점검 생략")
    args = ap.parse_args(argv)

    try:
        cfg = load_config()
    except ConfigError as e:
        print(f"[설정 오류] {e}")
        return 2

    if args.cmd == "snapshot":
        return cmd_snapshot(cfg)
    if args.cmd == "daily":
        cmd_daily(cfg, use_ai=not args.no_ai, deploy=not args.no_deploy)
    elif args.cmd == "probe":
        from tools.probe import run
        run(cfg)
    elif args.cmd == "build-site":
        cmd_build_site(cfg)
    elif args.cmd == "published-today":  # 오늘 판이 이미 있으면 0 (예비 발행이 중복되지 않게)
        from datetime import date
        done = any(e["date"] == date.today().isoformat() for e in storage.load_editions(storage.connect()))
        print("오늘 이미 발행됨 → 건너뜀" if done else "오늘 아직 발행 안 함 → 발행")
        return 0 if done else 1
    elif args.cmd == "cloud-setup":
        from trendbot.cloud_setup import main as setup_main
        return setup_main()
    elif args.cmd == "report":
        from trendbot.report import run as report_run
        print(report_run(cfg))
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
        from datetime import datetime
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        rows = [{"id": s["id"], "name": s["name"], "group": "community", "enabled": s.get("enabled", True),
                 "ok": s.get("enabled", True), "rows": 20, "at": now, "message": ""} for s in cfg["sources"]]
        rows += [{"id": k, "name": SIGNAL_NAMES.get(k, k), "group": "signal", "enabled": True, "ok": k != "ent_news",
                  "rows": 10, "at": now, "message": "timed out" if k == "ent_news" else ""}
                 for k, v in cfg["signals"].items() if v.get("enabled")]
        out = build(sample_editions(), rows)
        print(f"견본 사이트 생성: {out / 'index.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

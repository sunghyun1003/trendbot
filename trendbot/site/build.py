"""저장된 판(edition)들로 정적 웹사이트(public/)를 만듭니다."""

from __future__ import annotations

import json
import re
import shutil
from datetime import date as Date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from trendbot.config import DATA_DIR, ROOT, load_config

HERE = Path(__file__).parent
OUT = ROOT / "public"
FUNCTIONS_SRC = ROOT / "site_functions"
HELPER_SRC = ROOT / "tools" / "helper"


def package_helper(out: Path) -> None:
    """집 PC 도우미: 설치 스크립트 + 프로그램 묶음(helper.zip). 도우미 창구(/api/agent)로만 내려받음."""
    import zipfile

    folder = out / "helper"
    folder.mkdir(parents=True, exist_ok=True)
    shutil.copy2(HELPER_SRC / "install.ps1", folder / "install.ps1")
    with zipfile.ZipFile(folder / "helper.zip", "w", zipfile.ZIP_DEFLATED) as z:
        files = [(HELPER_SRC / "helper.py", "helper.py"), (ROOT / "config" / "sources.yaml", "config/sources.yaml")]
        files += [(f, f.relative_to(ROOT).as_posix()) for f in sorted((ROOT / "trendbot").rglob("*.py"))
                  if not {"site", "__pycache__"} & set(f.relative_to(ROOT).parts)]
        for f, name in files:  # 날짜를 고정해 내용이 같으면 묶음도 같게 (도우미가 쓸데없이 다시 받지 않음)
            z.writestr(zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0)), f.read_bytes(), zipfile.ZIP_DEFLATED)
WEEKDAYS = "월화수목금토일"
ORIGINAL_KEEP_DAYS = 30  # 원문 본문을 보관하는 기간


def _num(n) -> str:
    if n is None:
        return "-"
    n = int(n)
    if n >= 10_000:
        return f"{n / 10_000:.1f}".rstrip("0").rstrip(".") + "만"
    return f"{n:,}"


def _date_label(d: str) -> str:
    dt = Date.fromisoformat(d)
    return f"{dt.month}월 {dt.day}일({WEEKDAYS[dt.weekday()]})"


SHORT = {"디시": ("디시", "디시"), "웃긴대학": ("웃대", "웃대"), "루리웹": ("루리", "루리웹"), "디젤매니아": ("디젤", "디젤매니아"),
         "뽐뿌 핫딜": ("핫딜", "뽐뿌핫딜"), "뽐뿌": ("뽐뿌", "뽐뿌"), "클리앙": ("클량", "클리앙"), "보배드림": ("보배", "보배드림"),
         "인스티즈": ("인티", "인스티즈"), "더쿠": ("더쿠", "더쿠"), "네이트판": ("판", "네이트판"), "82쿡": ("82", "82쿡"),
         "유튜브": ("YT", "유튜브"), "에펨": ("펨코", "에펨"), "파우더룸": ("파룸", "파우더룸"), "스사사": ("스사사", "스사사"),
         "X": ("X", "X 트렌드"), "인스타": ("인스타", "인스타")}


def _short(name: str, i: int) -> str:
    for k, v in SHORT.items():
        if name.startswith(k):
            return v[i]
    return name[:2] if i == 0 else name[:5]


def _ytid(url: str | None) -> str | None:
    m = re.search(r"(?:v=|youtu\.be/|shorts/)([\w-]{11})", url or "")
    return m.group(1) if m else None


def _env() -> Environment:
    env = Environment(loader=FileSystemLoader(HERE / "templates"), autoescape=select_autoescape(["html"]))
    env.filters["num"] = _num
    env.filters["short"] = lambda n: _short(n, 0)
    env.filters["short_label"] = lambda n: _short(n, 1)
    env.filters["ytid"] = _ytid
    return env


def build(editions: list[dict], health: list[dict], out: Path = OUT) -> Path:
    editions = sorted(editions, key=lambda e: e["date"], reverse=True)
    if out.exists():
        shutil.rmtree(out)
    (out / "d").mkdir(parents=True)
    shutil.copytree(HERE / "static", out / "static")
    media_src = DATA_DIR / "media"
    env = _env()
    newest = Date.fromisoformat(editions[0]["date"]) if editions else None
    for e in editions:
        e["date_label"] = _date_label(e["date"])
        old = newest and (newest - Date.fromisoformat(e["date"])).days > ORIGINAL_KEEP_DAYS
        for c in e["cards"]:
            c["top"] = max(c["posts"], key=lambda p: p.get("views") or 0) if c["posts"] else None
            c["href"] = f"d/{e['date']}/{c['id']}.html"
        for ch in e["champions"]:
            if ch.get("post"):
                n = ch.get("in_card")
                ch["href"] = e["cards"][n - 1]["href"] if n and n <= len(e["cards"]) else f"d/{e['date']}/ch-{ch['source_id']}.html"
        if old:  # 오래된 판은 원문 본문·이미지를 지우고 링크만 남김
            for p in [p for c in e["cards"] for p in c["posts"]] + [ch["post"] for ch in e["champions"] if ch.get("post")]:
                p.pop("original", None)
        elif (media_src / e["date"]).exists():  # 보관 기간 안의 저장 이미지·캡처를 사이트에 함께 올림
            shutil.copytree(media_src / e["date"], out / "media" / e["date"], dirs_exist_ok=True)

    day = env.get_template("day.html")
    for e in editions:
        (out / "d" / f"{e['date']}.html").write_text(day.render(e=e, root="../", page="day"), encoding="utf-8")
    detail = env.get_template("detail.html")
    for e in editions:
        (out / "d" / e["date"]).mkdir(exist_ok=True)
        for c in e["cards"]:
            (out / c["href"]).parent.mkdir(parents=True, exist_ok=True)
            (out / c["href"]).write_text(detail.render(c=c, posts=c["posts"], back=f"../../d/{e['date']}.html#c-{c['id']}",
                                                       root="../../", page="detail"), encoding="utf-8")
        for ch in e["champions"]:
            if ch.get("post") and ch["href"].endswith(f"ch-{ch['source_id']}.html"):
                (out / ch["href"]).write_text(detail.render(c=None, ch_name=ch["name"], posts=[{**ch["post"], "source_name": ch["post"].get("source_name") or ch["name"]}],
                                                            back=f"../../d/{e['date']}.html", root="../../", page="detail"), encoding="utf-8")
    if editions:
        (out / "index.html").write_text(day.render(e=editions[0], root="", page="today"), encoding="utf-8")
    else:
        (out / "index.html").write_text("<!doctype html><meta charset=utf-8><p>아직 발행된 판이 없습니다.</p>", encoding="utf-8")

    rows = []
    for e in editions:
        for c in e["cards"]:
            rows.append({
                "date": e["date"], "id": c["id"], "headline": c["headline"], "field": c["field"], "grade": c["grade"],
                "score": c["score"], "pods": len(c["pods"]), "sites": c["spread"]["sites"],
                "views": max([p.get("views") or 0 for p in c["posts"]] or [0]),
                "comments": max([p.get("comments") or 0 for p in c["posts"]] or [0]),
                "titles": " ".join(p["title"] for p in c["posts"]),
                "vid": _ytid(c["videos"][0]["url"]) if c.get("videos") else None,
            })
    fields = sorted({r["field"] for r in rows})
    rows_json = json.dumps(rows, ensure_ascii=False).replace("</", "<\\/")
    (out / "archive.html").write_text(
        env.get_template("archive.html").render(editions=editions, rows=rows, rows_json=rows_json, fields=fields,
                                                channels=[s for s in load_config()["sources"] if s.get("enabled", True) and s.get("champion")],
                                                root="", page="archive"),
        encoding="utf-8")
    (out / "status.html").write_text(
        env.get_template("status.html").render(e=editions[0] if editions else None, sources=health, root="",
                                               page="status"),
        encoding="utf-8")
    # 채널 페이지: 날짜별 종합 1위 기록 + 조회·댓글·좋아요별 1위
    cfg = load_config()
    # 지금 꺼진 채널도 지난 판에 1위로 나온 적이 있으면 기록 페이지를 만듦 (링크가 깨지지 않게)
    seen = {c["source_id"] for e in editions for c in e["champions"]}
    channels = [src for src in cfg["sources"]
                if src.get("champion") and (src.get("enabled", True) or src["id"] in seen)]
    (out / "channel").mkdir(exist_ok=True)
    ch_tpl = env.get_template("channel.html")
    for src in channels:
        rows = []
        for e in editions:
            ch = next((c for c in e["champions"] if c["source_id"] == src["id"]), None)
            tops = (e.get("channel_tops") or {}).get(src["id"], {})
            best = ch["post"] if ch and ch.get("post") else None
            if not best and not tops:
                continue
            rows.append({"date": e["date"], "best": best, "href": ("../" + ch["href"]) if best and ch.get("href") else None,
                         "strength": ch.get("strength") if ch else None, **tops})
        (out / "channel" / f"{src['id']}.html").write_text(
            ch_tpl.render(src=src, rows=rows, pod_label=cfg["pods"][src["pod"]]["label"], root="../", page="archive"),
            encoding="utf-8")
    (out / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")
    (out / "_headers").write_text("/*\n  X-Robots-Tag: noindex, nofollow\n  Referrer-Policy: no-referrer\n", encoding="utf-8")
    package_helper(out)
    if FUNCTIONS_SRC.exists():
        shutil.copytree(FUNCTIONS_SRC, out / "functions")
    return out

"""저장된 판(edition)들로 정적 웹사이트(public/)를 만듭니다."""

from __future__ import annotations

import json
import re
import shutil
from datetime import date as Date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from trendbot.config import ROOT

HERE = Path(__file__).parent
OUT = ROOT / "public"
FUNCTIONS_SRC = ROOT / "site_functions"
WEEKDAYS = "월화수목금토일"


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
         "유튜브": ("YT", "유튜브"), "에펨": ("펨코", "에펨")}


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
    env = _env()
    for e in editions:
        e["date_label"] = _date_label(e["date"])
        for c in e["cards"]:
            c["top"] = max(c["posts"], key=lambda p: p.get("views") or 0) if c["posts"] else None

    day = env.get_template("day.html")
    for e in editions:
        (out / "d" / f"{e['date']}.html").write_text(day.render(e=e, root="../", page="day"), encoding="utf-8")
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
                                                root="", page="archive"),
        encoding="utf-8")
    (out / "status.html").write_text(
        env.get_template("status.html").render(e=editions[0] if editions else None, sources=health, root="",
                                               page="status"),
        encoding="utf-8")
    (out / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")
    (out / "_headers").write_text("/*\n  X-Robots-Tag: noindex, nofollow\n  Referrer-Policy: no-referrer\n", encoding="utf-8")
    if FUNCTIONS_SRC.exists():
        shutil.copytree(FUNCTIONS_SRC, out / "functions")
    return out

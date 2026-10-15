"""아침 요약 메일: 발행이 끝나면 '오늘 핵심 3 + 나머지 제목 + 신조어 풀이 + 링크'를 보냅니다.

보내는 계정: Gmail + 앱 비밀번호 (GitHub 비밀값 GMAIL_ADDRESS, GMAIL_APP_PASSWORD).
받는 사람: config/mail_to.txt (한 줄에 하나). 같은 날 두 번 보내지 않습니다.
"""

from __future__ import annotations

import os
import smtplib
import sqlite3
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape

from trendbot.config import ROOT

MAIL_TO = ROOT / "config" / "mail_to.txt"
GL = {"A": "전국 확산", "B": "확산 중", "M": "한 곳 대박"}
COLOR = {"A": "#f04452", "B": "#3182f6", "M": "#8b5cf6"}


def recipients() -> list[str]:
    if not MAIL_TO.exists():
        return []
    return [l.strip() for l in MAIL_TO.read_text(encoding="utf-8").splitlines()
            if l.strip() and not l.strip().startswith("#") and "@" in l]


def configured() -> bool:
    return bool(os.environ.get("GMAIL_ADDRESS") and os.environ.get("GMAIL_APP_PASSWORD") and recipients())


def _date_label(date: str) -> str:
    from datetime import date as D
    d = D.fromisoformat(date)
    return f"{d.month}월 {d.day}일({'월화수목금토일'[d.weekday()]})"


def compose(edition: dict, site: str) -> tuple[str, str, str]:
    """(제목, 글자 본문, HTML 본문)"""
    cards = edition["cards"]
    day = _date_label(edition["date"])
    subject = f"[ㄷㅅㅂㄱ] {day} 오늘의 피드 {len(cards)}건"
    link = lambda c: f"{site}/d/{edition['date']}.html#c-{c['id']}"
    top, rest = cards[:3], cards[3:]
    terms = [(t, c) for c in cards for t in c.get("terms") or []][:6]

    text = [subject, ""]
    text += ["■ 오늘 핵심"] + [f"{i}. [{GL[c['grade']]}] {c['headline']}\n   {c['why']}\n   {link(c)}" for i, c in enumerate(top, 1)]
    if rest:
        text += ["", "■ 그 밖에"] + [f"- {c['headline']}" for c in rest]
    if terms:
        text += ["", "■ 신조어·밈"] + [f"- {t['term']}: {t['meaning']}{'' if t.get('sure', True) else ' (추정)'}" for t, _ in terms]
    text += ["", f"전체 보기: {site}/d/{edition['date']}.html"]

    def item(i, c):
        life = (c.get("life") or {}).get("label")
        return (f'<tr><td style="padding:14px 0;border-bottom:1px solid #f2f4f6">'
                f'<div style="font-size:12px;font-weight:700;color:{COLOR[c["grade"]]}">{i:02d} · {GL[c["grade"]]}'
                f'{" · " + escape(life) if life else ""}</div>'
                f'<a href="{link(c)}" style="display:block;margin:4px 0;font-size:17px;font-weight:700;color:#191f28;text-decoration:none">{escape(c["headline"])}</a>'
                f'<div style="font-size:14px;line-height:1.5;color:#4e5968">{escape(c["why"])}</div></td></tr>')

    html = [f'<div style="max-width:560px;margin:0 auto;font-family:Pretendard,-apple-system,\'Apple SD Gothic Neo\',sans-serif;color:#191f28">',
            f'<div style="font-size:13px;color:#8b95a1">ㄷㅅㅂㄱ</div><h1 style="margin:4px 0 16px;font-size:22px">{day} · {len(cards)}건</h1>',
            '<table style="width:100%;border-collapse:collapse">', *[item(i, c) for i, c in enumerate(top, 1)], '</table>']
    if rest:
        html += ['<h2 style="margin:24px 0 8px;font-size:15px">그 밖에</h2><ul style="margin:0;padding-left:18px;font-size:14px;line-height:1.8">',
                 *[f'<li><a href="{link(c)}" style="color:#191f28">{escape(c["headline"])}</a></li>' for c in rest], '</ul>']
    if terms:
        html += ['<h2 style="margin:24px 0 8px;font-size:15px">신조어·밈</h2>',
                 *[f'<div style="font-size:14px;line-height:1.6;margin:4px 0"><b style="color:#3182f6">{escape(t["term"])}</b> '
                   f'{escape(t["meaning"])}{"" if t.get("sure", True) else " <span style=\'color:#8b95a1;font-size:12px\'>(추정)</span>"}</div>'
                   for t, _ in terms]]
    html += [f'<a href="{site}/d/{edition["date"]}.html" style="display:block;margin:28px 0;padding:14px;border-radius:12px;'
             f'background:#3182f6;color:#fff;text-align:center;font-weight:700;text-decoration:none">전체 피드 보기</a>',
             '<div style="font-size:12px;color:#8b95a1">팀 내부용 · 로그인한 팀원만 열람할 수 있어요</div></div>']
    return subject, "\n".join(text), "".join(html)


def send(edition: dict, site: str, db: sqlite3.Connection, smtp_factory=smtplib.SMTP_SSL) -> str:
    """보냈으면 결과 한 줄. 설정이 없거나 이미 보냈으면 건너뜀. 실패해도 발행에는 영향 없음."""
    if not configured():
        return "아침 메일: 설정 없음 (GMAIL_ADDRESS·GMAIL_APP_PASSWORD 비밀값, config/mail_to.txt)"
    if not edition["cards"]:
        return "아침 메일: 오늘 카드가 없어 보내지 않음"
    db.execute("CREATE TABLE IF NOT EXISTS mail_log (date TEXT PRIMARY KEY, sent_at TEXT NOT NULL)")
    if db.execute("SELECT 1 FROM mail_log WHERE date=?", (edition["date"],)).fetchone():
        return "아침 메일: 오늘 이미 보냄"
    subject, text, html = compose(edition, site.rstrip("/"))
    to = recipients()
    msg = MIMEMultipart("alternative")
    msg["Subject"], msg["From"], msg["To"] = subject, f"ㄷㅅㅂㄱ <{os.environ['GMAIL_ADDRESS']}>", ", ".join(to)
    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))
    with smtp_factory("smtp.gmail.com", 465, timeout=30) as s:
        s.login(os.environ["GMAIL_ADDRESS"], os.environ["GMAIL_APP_PASSWORD"])
        s.sendmail(os.environ["GMAIL_ADDRESS"], to, msg.as_string())
    from trendbot.models import now_iso
    db.execute("INSERT OR REPLACE INTO mail_log VALUES(?,?)", (edition["date"], now_iso()))
    db.commit()
    return f"아침 메일: {len(to)}명에게 보냄"

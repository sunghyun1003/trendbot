"""AI 편집자 (Claude Opus 5.5). 최종 후보에만 헤드라인·'왜 알아야 하나'·태그·제외 표시를 붙입니다.

AI가 실패하면 '편집자 부재' 모드로, 원제목과 근거만으로 카드를 만듭니다.
"""

from __future__ import annotations

import json
import os

import anthropic

from trendbot.config import RULES_PATH

MODEL = "claude-opus-5-5"
FIELDS = ["연예/방송", "음악", "스포츠", "게임", "IT", "패션/뷰티", "음식", "쇼핑/딜", "경제", "사회/사건",
          "정치", "생활/육아", "자동차", "여행", "기타"]
ATTRS = ["밈", "챌린지", "이슈/사건", "논란", "제품/딜", "음악", "장소", "인물", "캐릭터/IP", "정보", "콘텐츠",
         "광고/캠페인"]
EXCLUDE = ["없음", "광고", "중복", "신상", "내부싸움", "팬덤전용", "선정", "일상"]
HARD_EXCLUDE_OK_FOR_A = {"광고", "중복", "신상"}

SCHEMA = {
    "type": "object",
    "properties": {
        "cards": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "headline": {"type": "string"},
                    "why": {"type": "string"},
                    "field": {"type": "string", "enum": FIELDS},
                    "attributes": {"type": "array", "items": {"type": "string", "enum": ATTRS}},
                    "marketer": {"type": "string", "enum": ["활용 기회", "브랜드 주의", "없음"]},
                    "context": {"type": "string", "enum": ["확인", "제목만"]},
                    "exclude": {"type": "string", "enum": EXCLUDE},
                    "caution": {"type": "boolean"},
                },
                "required": ["id", "headline", "why", "field", "attributes", "marketer", "context", "exclude",
                             "caution"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["cards"],
    "additionalProperties": False,
}


def _brief(card: dict) -> dict:
    return {
        "id": card["id"],
        "grade": card["grade_label"],
        "evidence": card["evidence_line"],
        "titles": [f"[{p['source_name']}] {p['title']}" for p in card["posts"][:6]],
        "videos": [v["title"] for v in card["videos"][:3]],
        "search_keyword": card.get("anchor"),
        "news": card.get("news", [])[:4],
        "context_snippets": card.get("snippets", [])[:2],
    }


def edit(cards: list[dict]) -> tuple[dict[str, dict], str | None]:
    """{card_id: 편집 결과}, 오류 메시지(없으면 None)."""
    if not cards:
        return {}, None
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        return {}, "AI 키가 없어 편집자 부재 모드로 발행"
    rules = RULES_PATH.read_text(encoding="utf-8")
    payload = json.dumps([_brief(c) for c in cards], ensure_ascii=False, indent=1)
    client = anthropic.Anthropic(max_retries=2)
    try:
        resp = client.beta.messages.create(
            model=MODEL,
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=rules,
            output_config={"effort": "medium", "format": {"type": "json_schema", "schema": SCHEMA}},
            messages=[{"role": "user", "content": "오늘의 후보 카드입니다. 카드마다 하나씩 결과를 주세요.\n\n" + payload}],
        )
    except anthropic.APIError as e:
        return {}, f"AI 호출 실패: {e.__class__.__name__}"
    if resp.stop_reason == "refusal":
        return {}, "AI가 응답을 거부해 편집자 부재 모드로 발행"
    if resp.stop_reason == "max_tokens":
        return {}, "AI 응답이 잘려 편집자 부재 모드로 발행"
    text = next((b.text for b in resp.content if b.type == "text"), "")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {}, "AI 응답 형식 오류"
    return {c["id"]: c for c in data.get("cards", [])}, None


def apply(card: dict, result: dict | None) -> dict:
    """편집 결과를 카드에 붙임. A등급은 광고·중복·신상 외에는 제외 불가."""
    if not result:
        card.update(headline=card["posts"][0]["title"] if card["posts"] else card.get("anchor") or "",
                    why=card["evidence_line"], field=card.get("field_hint") or "기타", attributes=[],
                    marketer="없음", context="제목만", exclude="없음", caution=False, ai=False)
        return card
    exclude = result.get("exclude", "없음")
    caution = bool(result.get("caution"))
    if card["grade"] == "A" and exclude not in HARD_EXCLUDE_OK_FOR_A and exclude != "없음":
        exclude, caution = "없음", True
    headline = result["headline"]
    if result.get("context") == "제목만" and card["posts"]:
        headline = card["posts"][0]["title"]
    card.update(headline=headline, why=result["why"], field=result["field"], attributes=result["attributes"],
                marketer=result["marketer"], context=result["context"], exclude=exclude, caution=caution, ai=True)
    return card

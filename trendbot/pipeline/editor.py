"""AI 편집자 (Claude Sonnet 5.5). 최종 후보에만 헤드라인·'왜 알아야 하나'·태그·제외 표시를 붙입니다.

AI가 실패하면 '편집자 부재' 모드로, 원제목과 근거만으로 카드를 만듭니다.
"""

from __future__ import annotations

import base64
import json
import os

import anthropic

from trendbot.config import RULES_PATH

MODEL = "claude-sonnet-5-5"
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
                    "terms": {  # 신조어·밈 풀이 (없으면 빈 목록)
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {"term": {"type": "string"}, "meaning": {"type": "string"},
                                           "sure": {"type": "boolean"}},
                            "required": ["term", "meaning", "sure"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["id", "headline", "why", "field", "attributes", "marketer", "context", "exclude",
                             "caution", "terms"],
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


MAX_IMAGES_PER_CARD = 3
MAX_IMAGES_TOTAL = 60


def _image_block(path) -> dict | None:
    """저장된 원문 이미지를 긴 변 1024px로 줄여 AI에게 보낼 형태로 만듦."""
    from trendbot.collectors.media import to_webp

    try:
        data = to_webp(path.read_bytes(), max_side=1024)
    except OSError:
        return None
    if not data:
        return None
    return {"type": "image", "source": {"type": "base64", "media_type": "image/webp",
                                        "data": base64.standard_b64encode(data).decode()}}


def _content(cards: list[dict], payload: str) -> list[dict]:
    """카드 목록(JSON) + 카드별 대표 이미지(최대 3장). 이미지 위주 글도 내용을 보고 쓰게 함."""
    from trendbot.config import DATA_DIR

    blocks: list[dict] = [{"type": "text", "text": "오늘의 후보 카드입니다. 카드마다 하나씩 결과를 주세요.\n\n" + payload}]
    total = 0
    for c in cards:
        saved = [s for p in c["posts"][:1] for s in (p.get("original") or {}).get("saved", [])][:MAX_IMAGES_PER_CARD]
        imgs = [b for b in (_image_block(DATA_DIR / s["file"]) for s in saved) if b]
        if not imgs or total + len(imgs) > MAX_IMAGES_TOTAL:
            continue
        blocks.append({"type": "text", "text": f"카드 {c['id']}의 원문 이미지 {len(imgs)}장:"})
        blocks.extend(imgs)
        total += len(imgs)
    return blocks


def edit(cards: list[dict]) -> tuple[dict[str, dict], str | None]:
    """{card_id: 편집 결과}, 오류 메시지(없으면 None)."""
    if not cards:
        return {}, None
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        return {}, "AI 키가 없어 편집자 부재 모드로 발행"
    rules = RULES_PATH.read_text(encoding="utf-8")
    payload = json.dumps([_brief(c) for c in cards], ensure_ascii=False, indent=1)
    client = anthropic.Anthropic(max_retries=2)
    base = dict(model=MODEL, max_tokens=16000, system=rules,
                output_config={"effort": "medium", "format": {"type": "json_schema", "schema": SCHEMA}})
    # 요청이 거절(400)되면 원인이 될 만한 부분을 하나씩 빼고 다시 시도: ① 그대로 ② 이미지 없이 ③ 대체 모델 설정 없이
    attempts = [("기본", True, True), ("이미지 없이", False, True), ("대체 설정 없이", False, False)]
    resp, errors = None, []
    for label, with_images, with_fallback in attempts:
        content = _content(cards, payload) if with_images else [{"type": "text", "text": payload}]
        try:
            if with_fallback:
                resp = client.beta.messages.create(**base, betas=["server-side-fallback-2026-07-01"],
                                                   fallbacks="default",
                                                   messages=[{"role": "user", "content": content}])
            else:
                resp = client.messages.create(**base, messages=[{"role": "user", "content": content}])
            break
        except anthropic.BadRequestError as e:
            errors.append(f"{label}: {getattr(e, 'message', str(e))[:200]}")
            print(f"AI 요청 거절 ({label}): {getattr(e, 'message', str(e))[:300]}")
        except anthropic.APIError as e:
            return {}, f"AI 호출 실패: {e.__class__.__name__} {str(e)[:200]}"
    if resp is None:
        return {}, "AI 호출 실패: " + " / ".join(errors)
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


# AI가 없을 때 쓰는 단순 분야 추정 (제목·뉴스의 낱말로). 애매하면 '기타'.
FIELD_WORDS = {
    "스포츠": ["홈런", "감독", "선수", "야구", "축구", "kbo", "프로야구", "리그", "월드컵", "올림픽", "골", "경기", "mvp", "타율"],
    "연예/방송": ["배우", "아이돌", "걸그룹", "보이그룹", "드라마", "예능", "방송", "소속사", "연예인", "데뷔", "컴백", "출연", "멤버", "여돌", "남돌"],
    "음악": ["앨범", "음원", "콘서트", "차트", "신곡", "뮤비", "가수"],
    "게임": ["게임", "롤", "스팀", "닌텐도", "플스", "업데이트", "패치", "가챠"],
    "IT": ["아이폰", "갤럭시", "애플", "삼성전자", "ai", "앱", "구글", "챗gpt", "반도체", "해킹"],
    "경제": ["주식", "코스피", "환율", "금리", "부동산", "아파트값", "하이닉스", "물가", "증시", "코인"],
    "정치": ["대통령", "국회", "의원", "정부", "장관", "여당", "야당", "선거", "탄핵"],
    "사회/사건": ["체포", "경찰", "살해", "폭행", "흉기", "범인", "구속", "사망", "사고", "검찰", "재판", "칼부림", "절도"],
    "쇼핑/딜": ["할인", "특가", "핫딜", "쿠폰", "적립", "네이버페이", "품절", "출석"],
    "음식": ["맛집", "메뉴", "편의점", "라면", "치킨", "디저트", "급식"],
    "패션/뷰티": ["화장품", "코디", "패딩", "신발", "향수", "뷰티", "립"],
    "자동차": ["자동차", "신차", "전기차", "운전", "차량", "주차", "테슬라", "현대차", "블랙박스"],
    "여행": ["여행", "항공", "호텔", "공항", "관광"],
    "생활/육아": ["육아", "시어머니", "며느리", "결혼", "예식장", "엄마", "아이", "출산", "이혼"],
}


def guess_field(texts: list[str]) -> str:
    import re
    text = " ".join(texts).lower()
    words = set(re.findall(r"[가-힣a-z0-9]+", text))
    # 두 글자 이하 낱말('ai'·'롤'·'골')은 다른 말 속에 섞여 잘못 걸리므로 낱말 전체가 같을 때만 셈
    scores = {f: sum((w in words) if len(w) <= 2 else text.count(w) for w in ws) for f, ws in FIELD_WORDS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] else "기타"


def apply(card: dict, result: dict | None) -> dict:
    """편집 결과를 카드에 붙임. A등급은 광고·중복·신상 외에는 제외 불가."""
    if not result:
        card.update(headline=card["posts"][0]["title"] if card["posts"] else card.get("anchor") or "",
                    why=card["evidence_line"],
                    field=card.get("field_hint") or guess_field([p["title"] for p in card["posts"][:3]] + card.get("news", [])[:3]),
                    attributes=[],
                    marketer="없음", context="제목만", exclude="없음", caution=False, ai=False, terms=[])
        return card
    exclude = result.get("exclude", "없음")
    caution = bool(result.get("caution"))
    if card["grade"] == "A" and exclude not in HARD_EXCLUDE_OK_FOR_A and exclude != "없음":
        exclude, caution = "없음", True
    headline = result["headline"]
    if result.get("context") == "제목만" and card["posts"]:
        headline = card["posts"][0]["title"]
    card.update(headline=headline, why=result["why"], field=result["field"], attributes=result["attributes"],
                marketer=result["marketer"], context=result["context"], exclude=exclude, caution=caution, ai=True,
                terms=[t for t in (result.get("terms") or [])[:3] if t.get("term") and t.get("meaning")])
    return card

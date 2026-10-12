"""화면 확인용 견본 판. 모든 내용은 지어낸 것이며 실제 게시물이 아닙니다."""

from __future__ import annotations

import copy


def _post(src_id: str, name: str, title: str, views=None, likes=None, comments=None) -> dict:
    return {"source_id": src_id, "source_name": name, "title": title, "url": "#", "views": views, "likes": likes,
            "comments": comments, "rank": 1}


def _card(i, grade, badges, headline, why, field, attrs, age, marketer, path, posts, score, pods, sites,
          videos=None, subs=None, context="확인", caution=False) -> dict:
    return {"id": f"sample{i}", "grade": grade, "badges": badges, "headline": headline, "why": why, "field": field,
            "attributes": attrs, "age": age, "marketer": marketer, "context": context, "caution": caution,
            "path": path, "posts": posts, "videos": videos or [], "subs": subs or [], "score": score,
            "pods": pods, "spread": {"sites": sites, "pods": len(pods), "traffic": 0}, "tokens": [], "ai": True,
            "exclude": "없음"}


def sample_editions() -> list[dict]:
    cards = [
        _card(1, "A", ["NEW", "전국구", "남녀공통"], "[견본] 편의점 신상 디저트 '구름빵 크림' 품절 대란",
              "남초·여초 커뮤니티 4곳 베스트 동시 진입 + 구글 트렌드 5만+ (견본)", "음식", ["제품/딜", "밈"],
              "전 연령 (확산 기반 추정)", "활용 기회",
              [{"name": "웃긴대학", "at": "06:10"}, {"name": "디시 실시간 베스트", "at": "08:00"},
               {"name": "더쿠 HOT", "at": "11:20"}, {"name": "네이트판", "at": "15:00"}],
              [_post("theqoo", "더쿠 HOT", "[견본] 구름빵 크림 먹어본 후기 다들 어때", 81000, None, 1203),
               _post("dcbest", "디시 실시간 베스트", "[견본] 편의점 세 군데 돌았는데 다 품절", 180000, 2100, 640),
               _post("natepann", "네이트판", "[견본] 요즘 구름빵 크림 때문에 편의점 알바 힘들다", 52000, 310, 420)],
              96, ["P1", "P3", "P5", "P6"], 5,
              videos=[{"title": "[견본] 구름빵 크림 솔직 리뷰", "url": "#", "views": 1200000, "shorts": True}]),
        _card(2, "A", ["NEW", "전국구", "남녀공통"], "[견본] 지하철 안내방송 패러디 밈 확산",
              "커뮤니티 3개 독자층 + 유튜브 쇼츠 80만 회 (견본)", "생활/육아", ["밈"],
              "10~20대 남녀 중심 (확산 기반 추정)", "활용 기회",
              [{"name": "디시 실시간 베스트", "at": "02:40"}, {"name": "인스티즈", "at": "09:30"},
               {"name": "루리웹", "at": "12:10"}],
              [_post("dcbest", "디시 실시간 베스트", "[견본] 이번 역은 월요일입니다 ㅋㅋㅋ", 95000, 1800, 310),
               _post("instiz", "인스티즈", "[견본] 요즘 유행하는 안내방송 밈 모음", 40000, 900, 150)],
              82, ["P1", "P2", "P4"], 3),
        _card(3, "B", ["NEW", "급부상"], "[견본] 가을 한정 러닝화 컬러, 발매 하루 만에 리셀가 2배",
              "남성 20~30대 취미·30~50대 커뮤니티 + 구글 트렌드 2만+ (견본)", "패션/뷰티", ["제품/딜"],
              "남 20~50대 중심 (확산 기반 추정)", "활용 기회",
              [{"name": "디젤매니아", "at": "07:50"}, {"name": "뽐뿌 HOT", "at": "10:05"}],
              [_post("dieselmania", "디젤매니아", "[견본] 오늘 발매한 러닝화 실착 후기", 23000, 180, 410),
               _post("ppomppu_hot", "뽐뿌 HOT", "[견본] 러닝화 리셀가 미쳤네요", 31000, 45, 260)],
              54, ["P2", "P3"], 2),
        _card(4, "M", ["NEW", "단일채널 폭발"], "[견본] 신인 밴드 라이브 클립, 하루 만에 조회 140만",
              "유튜브 채널 평소 대비 12배 (견본)", "음악", ["음악", "콘텐츠"], "추정 불가", "없음", [],
              [], 30, ["P7"], 0,
              videos=[{"title": "[견본] 첫 단독 공연 라이브 클립", "url": "#", "views": 1400000, "shorts": False}]),
        _card(5, "B", ["업데이트", "급부상"], "[견본] 아파트 주차 갈등 글, 관리사무소 공식 입장 후 재확산",
              "어제 이후 새 독자층 2곳에 퍼짐 (견본)", "사회/사건", ["이슈/사건", "논란"],
              "여 30~50대 중심 (확산 기반 추정)", "브랜드 주의",
              [{"name": "네이트판", "at": "어제"}, {"name": "82쿡", "at": "09:20"}, {"name": "보배드림", "at": "13:40"}],
              [_post("natepann", "네이트판", "[견본] 주차 문제로 이웃과 갈등 후기", 120000, 900, 1500)],
              48, ["P3", "P6"], 3, context="제목만", caution=True),
    ]
    img = lambda a, b: ("data:image/svg+xml;utf8," + f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 800 600'>"
                         f"<defs><linearGradient id='g' x1='0' y1='0' x2='1' y2='1'><stop offset='0' stop-color='{a}'/>"
                         f"<stop offset='1' stop-color='{b}'/></linearGradient></defs><rect width='800' height='600' fill='url(%23g)'/>"
                         "<text x='400' y='318' font-size='40' text-anchor='middle' fill='white' font-family='sans-serif'>견본 이미지</text></svg>").replace("#", "%23")
    bodies = {
        0: ("[견본] 오늘 아침 편의점 세 군데 돌았는데 전부 품절이었음\n\n점원분 말로는 들어오자마자 10분 만에 다 나간대요.\n"
            "다들 어디서 구하셨어요? 저녁 입고 시간 아시는 분 공유 좀...", [img("%23ffd36b", "%23ff9a62")],
            [{"text": "[견본] 저녁 8시쯤 입고되는 곳이 많아요", "likes": 412}, {"text": "[견본] 이거 먹어보니까 왜 난리인지 알겠음", "likes": 230},
             {"text": "[견본] 재고 앱으로 확인하면 편해요", "likes": 118}]),
        1: ("[견본] 출근길 지하철에서 들은 안내방송 패러디가 계속 생각나서 올립니다.\n\n'이번 역은 월요일, 월요일역입니다. 내리실 문은 없습니다.'",
            [], [{"text": "[견본] 내리실 문은 없습니다 ㅋㅋㅋㅋ", "likes": 980}, {"text": "[견본] 목소리 지원 버전도 있음", "likes": 301}]),
    }
    for i, (body, imgs, cms) in bodies.items():
        cards[i]["posts"][0]["original"] = {"status": "ok", "body": body, "images": imgs, "comments": cms}
    cards[2]["posts"][0]["original"] = {"status": "login", "body": "", "images": [], "comments": []}
    cards[0]["posts"][1]["original"] = {"status": "ok", "body": "[견본] 세 군데 다 품절. 재입고 알림 신청했습니다.", "images": [], "comments": []}

    champs = [
        {"source_id": "dieselmania", "name": "디젤매니아", "post": cards[2]["posts"][0], "in_card": 3, "strength": "강함"},
        {"source_id": "ppomppu_hot", "name": "뽐뿌 HOT", "post": cards[2]["posts"][1], "in_card": 3, "strength": "강함"},
        {"source_id": "ppomppu_deal", "name": "뽐뿌 핫딜", "post": _post("ppomppu_deal", "뽐뿌 핫딜", "[견본] 무선 이어폰 역대가 특가", 41000, 88, 650), "strength": "평소 수준"},
        {"source_id": "dcbest", "name": "디시 실시간 베스트", "post": cards[0]["posts"][1], "in_card": 1, "strength": "역대급"},
        {"source_id": "theqoo", "name": "더쿠 HOT", "post": cards[0]["posts"][0], "in_card": 1, "strength": "강함"},
        {"source_id": "natepann", "name": "네이트판", "post": _post("natepann", "네이트판", "[견본] 시댁 김장 문제로 고민입니다", 98000, 1200, 2100), "strength": "평소 수준"},
        {"source_id": "instiz", "name": "인스티즈", "post": cards[1]["posts"][1], "in_card": 2, "strength": "평소 수준"},
        {"source_id": "clien", "name": "클리앙 추천글", "post": _post("clien", "클리앙", "[견본] 새 노트북 배터리 실측 결과", 21000, 140, 230), "strength": "평소 수준"},
        {"source_id": "ruliweb", "name": "루리웹 베스트", "post": _post("ruliweb", "루리웹", "[견본] 신작 게임 첫날 동접 기록", 45000, 520, 380), "strength": "강함"},
        {"source_id": "bobaedream", "name": "보배드림 베스트", "post": _post("bobaedream", "보배드림", "[견본] 블랙박스에 찍힌 아찔한 순간", 76000, 640, 510), "strength": "평소 수준"},
        {"source_id": "cook82", "name": "82쿡", "post": _post("cook82", "82쿡", "[견본] 김장 비용 올해 얼마나 드셨어요", 15000, None, 180), "strength": "평소 수준"},
        {"source_id": "humoruniv", "name": "웃긴대학", "post": _post("humoruniv", "웃긴대학", "[견본] 고양이 출근 저지 작전", 62000, 1300, 210), "strength": "평소 수준"},
        {"source_id": "youtube", "name": "유튜브 급상승", "post": {"title": "[견본] 첫 단독 공연 라이브 클립", "url": "#", "views": 1400000}, "strength": None},
    ]
    today = {
        "date": "2026-10-13", "generated_at": "2026-10-13T07:30:00+09:00", "cards": cards,
        "overflow": [{"id": "o1", "headline": "[견본] 정치 이슈 3번째 (분야 상한 초과)", "evidence": "포드 3곳"}],
        "excluded": [{"id": "x1", "headline": "[견본] 특정 브랜드 체험단 후기 다수", "reason": "광고"}],
        "champions": champs, "avg28": 9, "mood": "평소 수준",
        "health": {"total": 12, "ok": 11, "broken": [{"name": "에펨코리아 포텐", "message": "봇 차단"}]},
        "ai": {"used": True, "model": "claude-opus-5-5", "note": None}, "sample": True,
    }
    yesterday = {**today, "date": "2026-10-12", "generated_at": "2026-10-12T07:30:00+09:00",
                 "cards": copy.deepcopy(cards[1:3]), "mood": "조용한 날", "overflow": [], "excluded": [],
                 "champions": [{**copy.deepcopy(c), "in_card": None} for c in champs]}
    return [today, yesterday]

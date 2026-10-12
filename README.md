# ㄷㅅㅂㄱ (다시보기): 어제 인터넷, 꼭 알아야 할 것만

매일 아침 7:30에 **필수 카드 8~15장**과 **채널별 1위 한 줄씩**이 올라오는 팀 내부용 사이트입니다.

판정 기준은 **독자층이 다른 커뮤니티(남초·여초, 연령대)가 각자의 베스트 목록에 같은 이야기를 동시에 올렸는가**입니다. 여기에 검색·뉴스·유튜브 신호를 더합니다. 이 판정을 통과한 약 30건에만 AI 편집자(Claude Opus 5.5)가 헤드라인, '왜 알아야 하나' 한 줄, 태그를 붙입니다.

- 설계 문서: [docs/trend-archive-plan.md](docs/trend-archive-plan.md)
- 집 PC 설치: [docs/setup-home-pc.md](docs/setup-home-pc.md)
- 키 발급: [docs/keys-guide.md](docs/keys-guide.md)

## 구조

```
집 PC (항상 켜 둠)                              Cloudflare (무료)
  수집: 게시판 목록·구글 트렌드·뉴스·유튜브  ─┐
  네이버 카페: 로그인된 전용 브라우저로 읽기  ├→ SQLite → 판정 → AI 편집 → 정적 사이트 ─→ Pages + Access(팀원 로그인)
  예약: 윈도우 작업 스케줄러                  ─┘                                          ↑ 회사 PC는 브라우저로 열람만
```

| 경로 | 내용 |
|---|---|
| `config/sources.yaml` | 게시판 켜기/끄기, 독자층 묶음(포드), 채널 1위 목록, 판정 기준 |
| `config/editor_rules.md` | AI 편집자 하우스 룰 (한국어) |
| `trendbot/collectors/` | 게시판(설정 기반 범용 수집기), 네이버 카페, 구글 트렌드·뉴스, 유튜브 |
| `trendbot/pipeline/` | `cluster.py`(이야기 묶기), `grade.py`(등급·중복·채널 1위), `editor.py`(AI), `edition.py`(하루치 판 조립) |
| `trendbot/site/` | 정적 사이트 생성기와 화면 |
| `site_functions/api/feedback.js` | 피드백 버튼 저장 (Cloudflare Pages Function) |
| `tools/probe.py` | 집 PC 첫 점검 도구 |

## 명령어

```
python -m trendbot sample       # 견본 데이터로 화면 미리보기 (public/index.html)
python -m trendbot probe        # 집 PC 첫 점검
python -m trendbot snapshot     # 1회 수집 (--naver: 네이버 카페 포함)
python -m trendbot daily        # 오늘의 판 생성 + 사이트 배포 (--no-ai, --no-deploy)
python -m trendbot naver-login  # 네이버 직접 로그인 창
python -m trendbot pull-feedback # 팀원 피드백 가져오기 (daily에서 자동)
python -m trendbot doctor       # 설치·키·접속 한 번에 점검
python -m pytest                # 테스트
```

## 원칙

- 온도계용 수백 건은 제목·링크·수치만 저장합니다.
- 화면에 올라가는 글(하루 약 30개)만 원문 본문, 이미지, 베스트 댓글을 가져와 30일간 보여 줍니다.
  - 이미지는 집 PC가 내려받아 작게 줄인 사본(webp)으로 보여 줍니다. 받지 못했거나 영상·움짤이 있는 글은 본문 영역만 캡처합니다.
  - 30일이 지나면 본문·이미지·캡처를 지우고 링크만 남깁니다.
  - 댓글 닉네임과 프로필 사진은 남기지 않습니다.
- robots.txt를 지키고, 사이트당 요청 사이에 3초 간격을 둡니다.
- 자동 로그인과 차단 우회는 하지 않습니다.
- 사이트는 내부 열람 전용입니다(noindex, Cloudflare Access).

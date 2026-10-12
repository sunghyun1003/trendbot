# 집 PC 설치 안내서

집 PC에 트렌드 아카이브 수집기를 설치하는 방법입니다. 이 PC는 수집만 하고, 회사 PC에는 아무것도 설치하지 않습니다(회사에서는 완성된 사이트를 브라우저로 열기만 합니다).

윈도우 기준으로 적었습니다. 맥이라면 알려 주세요. 맥용 안내를 따로 드리겠습니다.

**걸리는 시간:** 처음 한 번, 약 40분

---

## 1단계. 프로그램 3개 설치 (15분)

| 프로그램 | 받는 곳 | 주의할 점 |
|---|---|---|
| Python 3.12 이상 | https://www.python.org/downloads/ | 설치 첫 화면에서 **"Add python.exe to PATH" 체크** |
| Git | https://git-scm.com/download/win | 기본값 그대로 "Next" |
| Node.js LTS | https://nodejs.org/ | 사이트 배포에 사용. 기본값 그대로 |

설치가 끝나면 **시작 메뉴 → "PowerShell"** 을 엽니다. 아래 명령은 모두 이 창에 붙여 넣고 Enter를 누르면 됩니다.

## 2단계. 코드 받기 (5분)

```powershell
cd $HOME
git clone https://github.com/sunghyun1003/trendbot.git
cd trendbot
git checkout claude/wizardly-edison-b339ub
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-home.txt
python -m playwright install chromium
```

- **기대 결과:** 마지막 줄까지 빨간 오류 없이 끝납니다.
- 저장소가 비공개이면 `git clone` 할 때 깃허브 로그인 창이 뜹니다. 로그인하면 됩니다.

## 3단계. 네이버 로그인 (3분)

```powershell
python -m trendbot naver-login
```

1. 전용 브라우저 창이 열리면 네이버에 **직접** 로그인합니다. 이때 '로그인 상태 유지'를 체크합니다.
2. 디젤매니아 카페(https://cafe.naver.com/dieselmania)에 한 번 들어가 인기글이 보이는지 확인합니다.
3. 창을 닫습니다.

- 이 창의 로그인 상태는 평소 쓰는 크롬과 분리되어 저장됩니다.
- 수집기는 비밀번호를 모르고, 자동 로그인도 하지 않습니다. 로그인이 풀리면 사이트의 '상태' 페이지에 "네이버 로그인 필요"가 뜹니다. 그때 이 단계만 다시 하면 됩니다.
- 권장: 평소 쓰는 네이버 주 계정 대신 **수집 전용 계정**을 쓰면 만일의 제재 위험을 줄일 수 있습니다.

## 4단계. 사이트 점검 1회 (10분)

```powershell
python -m trendbot probe
```

- 사이트마다 접속, 차단, 수집 허용 여부를 확인하고 화면 샘플을 저장합니다.
- 네이버 카페 점검 때는 브라우저 창이 잠깐 열렸다가 닫힙니다.
- **기대 결과:** 표가 출력되고 `data\probe_report.md` 파일이 생깁니다.

**점검 결과 올리기** (이 결과에 맞춰 Claude가 수집기를 고칩니다)

```powershell
git add -f data/probe_report.md tests/fixtures
git commit -m "집 PC 점검 결과"
git push
```

올린 다음에는 Claude Code에 **"점검 결과 올렸어"** 라고 말해 주세요.

## 5단계. 키 등록 (점검 후 수집기 수정이 끝나면)

**Anthropic API 키 넣는 법** (발급받은 키는 채팅에 붙여 넣지 마세요)
1. 저장소 폴더(`trendbot`)에서 `.env.example` 파일을 복사합니다.
2. 복사본 이름을 `.env`로 바꿉니다. 윈도우 탐색기에서 확장자가 보이지 않으면 `.env.txt`가 되지 않게 주의하세요.
3. 메모장으로 열어 `ANTHROPIC_API_KEY=` 뒤에 발급받은 키를 붙여 넣고 저장합니다. 예: `ANTHROPIC_API_KEY=sk-ant-...`
4. 확인: `python -m trendbot daily --no-deploy`를 실행했을 때 "AI 키가 없어" 문구가 나오지 않으면 연결된 것입니다.

`.env` 파일은 저장소에 올라가지 않도록 막혀 있습니다(.gitignore). 나머지 키도 같은 파일에 함께 적습니다.

`.env.example` 파일을 복사해 이름을 `.env`로 바꾸고, 메모장으로 열어 아래 값을 채웁니다.

| 항목 | 받는 곳 | 비용 |
|---|---|---|
| `ANTHROPIC_API_KEY` | https://console.anthropic.com → API Keys | 월 약 $12~20 |
| `YOUTUBE_API_KEY` | Google Cloud 콘솔 → "YouTube Data API v3" 사용 설정 → 사용자 인증 정보 → API 키 | 무료 |
| `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID` | Cloudflare 가입 → My Profile → API Tokens → "Cloudflare Pages: Edit" 권한 | 무료 |

## 6단계. 사이트 공개 범위 잠그기 (Cloudflare, 10분)

1. Cloudflare 대시보드 → Workers & Pages에서 `trendbot` 프로젝트를 만듭니다. 첫 배포는 `python -m trendbot daily`가 자동으로 합니다.
2. Zero Trust → Access → Applications에서 `trendbot.pages.dev`를 등록하고, 정책을 "허용: 본인과 팀원 이메일"로 정합니다.
3. 프로젝트 설정 → Access policy에서 **미리보기 주소(*.trendbot.pages.dev)도 보호**를 켭니다.
4. 피드백 버튼용 설정입니다.
   - Settings → Functions → KV namespace bindings에서 이름 `FEEDBACK`으로 KV 저장소를 연결합니다.
   - 환경 변수에 `ACCESS_TEAM_DOMAIN`(예: yourteam.cloudflareaccess.com)과 `ACCESS_AUD`(Access 앱의 Application Audience 값)를 넣습니다.
5. **확인:** 시크릿 창에서 사이트 주소를 열었을 때 로그인 화면이 떠야 합니다.

## 7단계. 자동 실행 등록 (3분)

PowerShell을 **관리자 권한으로 실행**한 뒤 아래 명령을 넣습니다.

```powershell
cd $HOME\trendbot
powershell -ExecutionPolicy Bypass -File tools\install_schedule.ps1
```

등록되는 일정은 다음과 같습니다. 실행할 때마다 최신 코드를 자동으로 받습니다.

| 시각 | 하는 일 |
|---|---|
| 01:30, 12:00, 22:00 | 커뮤니티·검색·영상 수집 |
| 06:30, 17:00 | 위와 같음 + 네이버 카페 |
| 07:00 | 오늘의 판 만들기 → 사이트 배포 (07:30 전 완료) |

**PC 설정**
- 설정 → 시스템 → 전원에서 **"절전 모드: 안 함"** 으로 둡니다. 예약 작업에 '절전 해제' 옵션이 들어 있지만, 끄지 않는 편이 가장 확실합니다.
- 윈도우 업데이트는 '사용 시간'을 새벽 1~7시 밖으로 설정해 이 시간에 재부팅되지 않게 합니다.

## 문제가 생겼을 때

| 증상 | 할 일 |
|---|---|
| 사이트 '상태'에 모든 소스가 고장 | 집 PC가 꺼졌거나 인터넷이 끊김 → PC 켜기 |
| "네이버 로그인 필요" | 3단계 다시 하기 |
| 한 사이트만 고장 | Claude Code에 "고장 수리: (사이트 이름)" 요청 |
| 실행 기록 보기 | `data\logs\run.log` 파일 |

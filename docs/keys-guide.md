# 키 발급 안내서

ㄷㅅㅂㄱ를 돌리는 데 필요한 키를 발급받는 순서입니다. 발급한 키는 마지막에 집 PC의 `.env` 파일에 한꺼번에 넣습니다.

**넣기 전에 꼭 지킬 것**
- 키는 비밀번호와 같습니다. 채팅, 메일, 단톡방에 붙여 넣지 마세요.
- 키는 `.env` 파일에만 적습니다. 이 파일은 저장소에 올라가지 않게 막혀 있습니다.
- 잃어버리거나 새어 나갔다 싶으면 같은 화면에서 지우고 새로 만들면 됩니다.

| # | 무엇 | 꼭 필요? | 비용 | 걸리는 시간 |
|---|---|---|---|---|
| 1 | Anthropic API 키 | 필수 (AI 편집자) | 쓴 만큼, 월 약 $25~35 | 5분 |
| 2 | YouTube Data API 키 | 권장 (유튜브 급상승) | 무료 | 10분 |
| 3 | Cloudflare 계정 ID와 API 토큰, 사이트 잠금(Access) | 필수 (사이트 올리기) | 무료 | 20분 |
| 4 | 피드백 가져오기용 서비스 토큰과 EXPORT_TOKEN | 선택 (유지/제외 버튼 기록) | 무료 | 10분 |
| 5 | GitHub 로그인 | 필수 (집 PC가 코드 받기) | 무료 | 2분 |

---

## 1. Anthropic API 키 (AI 편집자)

1. https://console.anthropic.com 에 접속해 로그인합니다. 이미 발급받으셨다면 4번으로 바로 가세요.
2. 왼쪽 메뉴 **Billing(결제)** 에서 카드를 등록하고 크레딧을 충전합니다. 처음에는 $20 정도면 충분합니다.
   - **Auto-reload(자동 충전)** 는 꺼 두고, 잔액이 떨어지면 메일이 오도록 알림만 켜 두는 것을 권장합니다.
3. **Limits(사용 한도)** 에서 월 사용 한도를 $50 정도로 걸어 두면, 혹시 뭔가 잘못돼도 그 이상은 나가지 않습니다.
4. **API Keys** → **Create Key** 를 누르고, 이름을 `dsbg-home-pc`로 지어 만듭니다.
5. `sk-ant-`로 시작하는 키가 **한 번만** 보입니다. 바로 복사해 두세요.

- **넣는 곳:** `.env`의 `ANTHROPIC_API_KEY=` 뒤
- **예상 비용**
  - 하루 후보 약 30건과 대표 이미지(카드당 최대 3장)를 Opus 5.5가 읽습니다. 월 약 $25~35입니다.
  - 키가 없거나 크레딧이 떨어지면 사이트는 멈추지 않고 '원제목 그대로' 발행됩니다.

## 2. YouTube Data API 키 (유튜브 급상승 영상)

1. https://console.cloud.google.com 에 구글 계정으로 접속합니다.
2. 위쪽 프로젝트 선택 → **새 프로젝트** → 이름 `dsbg` → 만들기
3. 왼쪽 메뉴 **API 및 서비스 → 라이브러리** → "YouTube Data API v3" 검색 → **사용**
4. **API 및 서비스 → 사용자 인증 정보** → **사용자 인증 정보 만들기 → API 키**
5. 만들어진 키를 눌러 **키 제한**을 설정하고 저장합니다.
   - API 제한사항: "키 제한" → **YouTube Data API v3만** 선택
   - (선택) 애플리케이션 제한사항: IP 주소 → 집 PC의 공인 IP

- **넣는 곳:** `.env`의 `YOUTUBE_API_KEY=` 뒤
- **비용:** 무료입니다. 하루 10,000유닛을 주는데 우리는 하루 약 450유닛을 씁니다. 카드 등록도 필요 없습니다.

## 3. Cloudflare (사이트 올리기와 잠금)

### 3-1. 가입과 계정 ID
1. https://dash.cloudflare.com/sign-up 에서 회사 메일로 가입합니다(무료 플랜).
2. 대시보드 오른쪽 아래 또는 **Workers & Pages** 화면 오른쪽의 **Account ID** 를 복사합니다.

- **넣는 곳:** `.env`의 `CLOUDFLARE_ACCOUNT_ID=` 뒤

### 3-2. API 토큰 (집 PC가 사이트를 올릴 때 사용)
1. 오른쪽 위 사람 아이콘 → **My Profile → API Tokens → Create Token**
2. **Create Custom Token** 을 고릅니다.
   - 이름: `dsbg-deploy`
   - 권한(Permissions): **Account → Cloudflare Pages → Edit** 하나만
   - 계정(Account Resources): 내 계정
3. **Continue to summary → Create Token** 을 누르고, 나온 토큰을 복사합니다(한 번만 보임).

- **넣는 곳:** `.env`의 `CLOUDFLARE_API_TOKEN=` 뒤

### 3-3. 첫 배포
키를 다 넣은 뒤 집 PC에서 `python -m trendbot daily`를 한 번 실행하면 `trendbot` 프로젝트가 자동으로 만들어집니다. 사이트 주소는 `https://trendbot.pages.dev`이고, 이름이 겹치면 뒤에 글자가 붙습니다.

### 3-4. 사이트 잠그기 (팀원만 보기) — 첫 배포 직후 반드시
1. 대시보드 왼쪽 **Zero Trust** 를 엽니다. 처음이면 팀 이름을 정하고 **Free 플랜**(50명까지 무료)을 고릅니다.
   - 팀 이름이 `dsbg`라면 팀 도메인은 `dsbg.cloudflareaccess.com`입니다.
2. **Access → Applications → Add an application → Self-hosted** 를 고릅니다.
   - Application name: `ㄷㅅㅂㄱ`
   - Domain: `trendbot.pages.dev`를 넣고, 같은 앱에 `*.trendbot.pages.dev`(미리보기 주소)도 추가합니다.
3. 정책(Policy)을 만듭니다.
   - 이름: `팀원`, Action: **Allow**
   - Include → **Emails** → 본인과 팀원 메일 주소들
   - (4번을 할 경우) 정책을 하나 더 만듭니다: Action **Service Auth**, Include → **Service Token** → 4번에서 만든 토큰
4. 저장한 뒤 앱 상세 화면의 **Application Audience (AUD) Tag** 값을 복사해 둡니다(3-5에서 씀).
5. **확인:** 시크릿 창으로 사이트 주소를 열면 이메일 로그인 화면이 떠야 합니다.

### 3-5. 피드백 버튼 저장소 연결
1. **Workers & Pages → KV → Create a namespace** 에서 이름 `dsbg-feedback`으로 만듭니다.
2. **Workers & Pages → trendbot → Settings → Bindings → Add → KV namespace**
   - 변수 이름: `FEEDBACK`
   - 연결할 저장소: `dsbg-feedback`
3. 같은 Settings 화면의 **Variables and Secrets** 에 세 가지를 추가합니다.
   - `ACCESS_TEAM_DOMAIN` = `dsbg.cloudflareaccess.com` (내 팀 도메인)
   - `ACCESS_AUD` = 3-4에서 복사한 AUD 값
   - `EXPORT_TOKEN` = 4-2에서 만든 값 (4번을 할 경우)
4. 한 번 더 배포하면 적용됩니다.

## 4. 피드백 가져오기 (선택)

팀원이 누른 유지/제외/놓친 것 기록을 집 PC로 가져와, 판정 기준을 조정하는 데 씁니다.

### 4-1. 서비스 토큰 (집 PC가 잠긴 사이트에 들어갈 때 쓰는 출입증)
1. **Zero Trust → Access → Service Auth → Create Service Token** 을 누르고, 이름을 `dsbg-home-pc`로 지어 만듭니다.
2. 나온 **Client ID** 와 **Client Secret** 을 복사합니다. Secret은 한 번만 보입니다.
3. 3-4의 3번처럼 이 토큰을 허용하는 Service Auth 정책을 추가합니다.

- **넣는 곳:** `.env`의 `CF_ACCESS_CLIENT_ID=`, `CF_ACCESS_CLIENT_SECRET=` 뒤, 그리고 `SITE_URL=` 뒤에 사이트 주소(예: `https://trendbot.pages.dev`)

### 4-2. EXPORT_TOKEN (직접 만드는 비밀 문자열)
집 PC의 PowerShell에서 아래 한 줄을 실행하고, 나온 문자열을 씁니다.
```powershell
python -c "import secrets; print(secrets.token_urlsafe(32))"
```
- **넣는 곳:** 두 군데에 같은 값을 넣습니다.
  - `.env`의 `EXPORT_TOKEN=` 뒤
  - Cloudflare 3-5의 `EXPORT_TOKEN`

## 5. GitHub 로그인 (집 PC가 코드를 받을 때)
- 별도 키를 만들 필요는 없습니다.
- 집 PC에서 처음 `git clone`을 하면 브라우저 로그인 창이 뜹니다. `sunghyun1003` 계정으로 로그인하면 끝입니다(Git Credential Manager가 기억함).

---

## 마지막에 완성된 `.env` 모습

```
ANTHROPIC_API_KEY=sk-ant-api03-...
YOUTUBE_API_KEY=AIza...
CLOUDFLARE_ACCOUNT_ID=0123abcd...
CLOUDFLARE_API_TOKEN=abcd...
CF_PAGES_PROJECT=trendbot
SITE_URL=https://trendbot.pages.dev
CF_ACCESS_CLIENT_ID=xxxx.access
CF_ACCESS_CLIENT_SECRET=yyyy...
EXPORT_TOKEN=zzzz...
```

다 넣었으면 집 PC에서 아래를 실행합니다. ✗가 있는 줄에는 고치는 방법이 함께 나옵니다.
```powershell
python -m trendbot doctor
```

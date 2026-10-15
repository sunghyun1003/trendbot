# 키 발급 안내서

ㄷㅅㅂㄱ를 돌리는 데 필요한 키를 발급받아 **한 곳**에 넣는 방법입니다. 프로그램 설치나 명령어 입력은 없고, 전부 웹사이트에서 합니다.

## 넣는 곳은 딱 한 곳: GitHub '비밀값' 화면

👉 https://github.com/sunghyun1003/trendbot/settings/secrets/actions/new

1. 위 주소를 열면 **New secret** 화면이 나옵니다.
2. **Name** 칸에 아래 표의 이름을 그대로 적습니다(대문자, 밑줄까지 똑같이).
3. **Secret** 칸에 발급받은 값을 붙여 넣고 **Add secret**을 누릅니다.
4. 키마다 반복합니다.

사이트가 생긴 뒤에는 사이트의 **상태** 화면에서 키마다 ✓/✗ 표시를 보고, ✗ 옆 '넣기' 링크로 바로 이 화면에 올 수 있습니다.

**꼭 지킬 것**
- 키는 비밀번호와 같습니다. 채팅, 메일, 단톡방(Claude와의 대화 포함)에 붙여 넣지 마세요.
- 한 번 넣은 값은 GitHub도 다시 보여 주지 않습니다. 바꾸려면 같은 이름으로 다시 넣으면 됩니다.
- 새어 나갔다 싶으면 발급한 사이트에서 지우고 새로 만들어 다시 넣으세요.

| # | Name (이름) | 무엇 | 꼭 필요? | 비용 | 시간 |
|---|---|---|---|---|---|
| 1 | `ANTHROPIC_API_KEY` | AI 편집자 | 필수 | 월 약 $25~35 | 5분 |
| 2 | `CLOUDFLARE_ACCOUNT_ID` | 사이트를 올릴 Cloudflare 계정 | 필수 | 무료 | 3분 |
| 3 | `CLOUDFLARE_API_TOKEN` | Cloudflare 작업 허가증 | 필수 | 무료 | 5분 |
| 4 | (넣을 값 없음) | Cloudflare 팀 로그인(Zero Trust) 시작 | 필수 | 무료 | 5분 |
| 5 | `ALLOWED_EMAILS` | 사이트를 볼 팀원 이메일 | 필수 | — | 1분 |
| 6 | `DASHBOARD_TOKEN` | 사이트의 버튼(지금 수집, 켜기·끄기)용 GitHub 허가증 | 필수 | 무료 | 5분 |
| 7 | `YOUTUBE_API_KEY` | 유튜브 급상승·인기 차트 | 선택 | 무료 | 10분 |
| 8 | `SITE_DOMAIN` | 내 도메인 주소 (예: `dsbg.mydomain.com`) | 선택 | 도메인 구입비 | 20분 |
| 9 | `META_ACCESS_TOKEN`, `IG_USER_ID` | 인스타 감시 계정 | 선택 (나중에) | 무료 | 30분 |

---

## 1. ANTHROPIC_API_KEY (AI 편집자)

1. https://console.anthropic.com 에 로그인합니다. 이미 발급받은 키가 있으면 5번으로 바로 가세요.
2. **Billing(결제)** 에서 카드를 등록하고 크레딧을 $20 정도 충전합니다.
   - **Auto-reload(자동 충전)** 는 꺼 두고, 잔액 알림만 켜 두는 것을 권장합니다.
3. **Limits(사용 한도)** 에서 월 한도를 $50 정도로 걸어 둡니다. 뭔가 잘못돼도 그 이상은 나가지 않습니다.
4. **API Keys → Create Key**, 이름은 `dsbg`로 만듭니다.
5. `sk-ant-`로 시작하는 키가 **한 번만** 보입니다. 바로 복사해 GitHub 비밀값 `ANTHROPIC_API_KEY`로 넣습니다.

- 키가 없거나 크레딧이 떨어져도 사이트는 멈추지 않습니다. AI 요약 없이 원제목 그대로 발행됩니다.

## 2. CLOUDFLARE_ACCOUNT_ID (사이트를 올릴 계정)

1. https://dash.cloudflare.com/sign-up 에서 가입합니다(무료 플랜).
2. 로그인 후 왼쪽 **Workers & Pages** 를 누르면 오른쪽에 **Account ID** 가 보입니다. 복사합니다.
3. GitHub 비밀값 `CLOUDFLARE_ACCOUNT_ID`로 넣습니다.

## 3. CLOUDFLARE_API_TOKEN (Cloudflare 작업 허가증)

GitHub 서버가 사이트를 만들고 올리고 잠글 때 쓰는 허가증입니다.

1. 오른쪽 위 사람 아이콘 → **My Profile → API Tokens → Create Token → Create Custom Token(Get started)**
2. 이름: `dsbg`
3. **Permissions**에 아래 5줄을 만듭니다(줄 추가는 **+ Add more**). 5줄 모두 왼쪽 칸은 **Account**, 오른쪽 칸은 **Edit**입니다.

   | 가운데 칸 |
   |---|
   | Cloudflare Pages |
   | Workers KV Storage |
   | Access: Apps and Policies |
   | Access: Organizations, Identity Providers, and Groups |
   | Workers Scripts |

4. **Account Resources**: Include → 내 계정
5. **Continue to summary → Create Token**. 나온 토큰을 복사해(한 번만 보임) GitHub 비밀값 `CLOUDFLARE_API_TOKEN`으로 넣습니다.

**이미 토큰을 만들었다면 (Workers Scripts 줄 추가만)**
- 'Workers Scripts'는 매일 06:30 정시 발행용 '정시 실행기'에 필요합니다.
- My Profile → API Tokens → 만든 `dsbg` 토큰 오른쪽 **⋯ → Edit** → **+ Add more** → Account · **Workers Scripts** · **Edit** → **Continue to summary → Update Token**
- 토큰 값은 그대로라 GitHub 비밀값은 바꾸지 않아도 됩니다. '처음 설정'만 다시 누르세요.

## 4. Cloudflare Zero Trust 시작 (팀원 로그인 기능, 넣을 값 없음)

사이트를 팀원만 볼 수 있게 잠그는 기능입니다. 처음 한 번 '시작'만 눌러 두면, 잠금 설정은 '처음 설정'이 자동으로 합니다.

1. Cloudflare 대시보드 왼쪽 메뉴 **Zero Trust**
2. 팀 이름을 정합니다(예: `dsbg-team`). 팀원 로그인 화면 주소에 쓰입니다.
3. 요금제는 **Free(무료, 50명까지)** 를 고릅니다.
   - 카드 등록을 요구할 수 있습니다. 무료 요금제라 청구 금액은 ₩0입니다.
4. 완료 화면이 나오면 끝입니다. 다른 설정은 건드리지 않아도 됩니다.

## 5. ALLOWED_EMAILS (사이트를 볼 팀원)

- 값: 볼 사람의 이메일을 쉼표로 이어 적습니다. 예: `me@company.com, teammate@company.com`
- 팀원은 사이트에 들어갈 때 이메일로 온 6자리 번호로 로그인합니다(별도 가입 없음).
- 사람을 추가·삭제할 때는 이 값을 고친 뒤 '처음 설정'을 다시 한 번 실행하면 반영됩니다.

## 6. DASHBOARD_TOKEN (사이트 버튼용 GitHub 허가증)

사이트의 '지금 수집', '지금 발행', '사이트 켜기·끄기' 버튼과 키 ✓/✗ 표시가 쓰는 허가증입니다.

1. https://github.com/settings/personal-access-tokens/new 를 엽니다.
2. 아래처럼 고릅니다.
   - **Token name**: `dsbg-dashboard`
   - **Expiration**: 1년(최대). 만료되면 사이트 '상태' 화면 버튼이 동작하지 않으니, 그때 새로 만들어 같은 이름으로 다시 넣습니다.
   - **Repository access**: **Only select repositories** → `trendbot`
   - **Permissions → Repository permissions** 에서 3가지만:
     - **Actions**: Read and write
     - **Contents**: Read and write
     - **Secrets**: Read-only (값은 못 보고 이름만 확인)
3. **Generate token** → `github_pat_`로 시작하는 값을 복사해 GitHub 비밀값 `DASHBOARD_TOKEN`으로 넣습니다.

## 7. YOUTUBE_API_KEY (선택: 유튜브 급상승)

비워 두면 유튜브 신호만 빠지고 나머지는 그대로 돌아갑니다.

1. https://console.cloud.google.com 에 구글 계정으로 접속합니다.
2. 위쪽 프로젝트 선택 → **새 프로젝트** → 이름 `dsbg` → 만들기
3. **API 및 서비스 → 라이브러리** → "YouTube Data API v3" → **사용**
4. **API 및 서비스 → 사용자 인증 정보 → 사용자 인증 정보 만들기 → API 키**
5. 만든 키의 **API 제한사항**을 'YouTube Data API v3만'으로 설정하고 저장합니다.
6. GitHub 비밀값 `YOUTUBE_API_KEY`로 넣습니다.

- 비용은 무료입니다(하루 한도 10,000 중 약 450 사용, 카드 등록 불필요).

## 8. SITE_DOMAIN (Hostinger에서 산 내 도메인 연결)

`dsbg.pages.dev` 대신 내 주소(예: `dsbg.mydomain.com`)로 열고 싶을 때만 합니다.

1. **Hostinger에서 도메인 구입**: hostinger.com → 도메인 검색 → 구입. 호스팅 상품은 필요 없습니다.
2. **Cloudflare에 도메인 등록**
   - dash.cloudflare.com → **Add a domain(도메인 추가)** → 산 도메인 입력(예: `mydomain.com`)
   - 요금제는 **Free** → 계속 누르면 **네임서버 2개**(예: `ada.ns.cloudflare.com`, `bob.ns.cloudflare.com`)가 나옵니다. 이 화면을 열어 둡니다.
3. **Hostinger에서 네임서버 바꾸기**
   - Hostinger hPanel → **도메인** → 산 도메인 → **DNS / 네임서버** → **네임서버 변경**
   - '사용자 지정 네임서버'를 고르고 2번의 Cloudflare 네임서버 2개를 넣고 저장합니다.
4. **기다리기**: Cloudflare가 "도메인이 활성화됐다"는 메일을 보냅니다(보통 몇 분, 길면 24시간).
5. **GitHub 비밀값 `SITE_DOMAIN`** 에 쓸 주소를 넣습니다.
   - 도메인 전체를 쓰려면 `mydomain.com`
   - 하위 주소를 쓰려면 `dsbg.mydomain.com` (권장: 나중에 도메인을 다른 용도로도 쓸 수 있음)
6. **'처음 설정'을 다시 한 번** 누릅니다. 새 주소를 사이트에 붙이고, **팀원 로그인 잠금도 새 주소에 함께** 겁니다.
7. 몇 분 뒤 새 주소로 들어가 6자리 번호 로그인이 뜨면 끝입니다. 기존 `pages.dev` 주소도 계속 열립니다(역시 잠김).

- 3번에서 Hostinger가 "Cloudflare 네임서버로 바꾸면 Hostinger 메일·사이트가 멈춘다"고 경고할 수 있습니다. 이 도메인을 ㄷㅅㅂㄱ에만 쓴다면 무시해도 됩니다.

## 9. 인스타그램 (나중에: Meta 개발자 사이트 접속이 되는 PC에서)

인스타 비즈니스 계정 전환과 페이스북 페이지 연결은 끝난 상태라는 전제입니다.

1. https://developers.facebook.com → 로그인 → **내 앱 → 앱 만들기** → 사용 사례 '기타' → 앱 유형 **비즈니스** → 이름 `dsbg`
2. 앱 대시보드에서 **Instagram Graph API(Facebook 로그인으로 Instagram API)** 제품을 추가합니다.
3. **도구 → 그래프 API 탐색기**
   - 오른쪽 위 앱에서 `dsbg` 선택
   - 권한 추가: `instagram_basic`, `pages_show_list`, `pages_read_engagement`, `business_management`
   - **Generate Access Token** → 페이스북 로그인 창에서 연결한 페이지·인스타 계정을 체크하고 허용
4. 탐색기 주소창에 `me/accounts?fields=name,access_token,instagram_business_account` 를 넣고 **제출**
   - 결과에서 내 페이지의 `access_token` 값 → GitHub 비밀값 `META_ACCESS_TOKEN`
   - `instagram_business_account` 안의 `id` 값 → GitHub 비밀값 `IG_USER_ID`
   - 이 페이지 토큰은 3번 토큰이 '장기 토큰'일 때 만료가 없습니다. 탐색기 토큰은 1시간짜리라, 처음엔 [액세스 토큰 디버거](https://developers.facebook.com/tools/debug/accesstoken/)에서 **액세스 토큰 연장**을 눌러 장기 토큰으로 바꾼 뒤 4번을 다시 실행하세요.
5. 사이트 **상태** 탭 → '인스타 감시 계정'에 계정을 적고 저장합니다.
6. 상태 탭 키 목록에 두 키가 ✓로 바뀌면 다음 수집부터 동작합니다.

---

다 넣었으면 [시작 안내서](start-guide.md)의 2단계 '처음 설정'으로 넘어가세요.

## 10. 아침 요약 메일 (GMAIL_ADDRESS, GMAIL_APP_PASSWORD)

매일 피드가 올라가면 `config/mail_to.txt`에 적힌 주소로 요약 메일을 보냅니다. 보내는 계정은 개인 Gmail입니다.

1. 휴대폰이나 PC에서 https://myaccount.google.com/security 를 엽니다.
2. **2단계 인증**이 꺼져 있으면 켭니다. 앱 비밀번호를 만들려면 꼭 필요합니다.
3. https://myaccount.google.com/apppasswords 에서 이름에 `dsbg`를 적고 **만들기**를 누릅니다.
4. 노란 상자에 나온 16자리(예: `abcd efgh ijkl mnop`)를 복사합니다. 창을 닫으면 다시 볼 수 없습니다.
5. GitHub 비밀값에 두 개를 넣습니다.
   - `GMAIL_ADDRESS`: 보내는 Gmail 주소 (예: `내아이디@gmail.com`)
   - `GMAIL_APP_PASSWORD`: 방금 복사한 16자리

- 받는 사람을 바꾸려면 GitHub에서 `config/mail_to.txt`를 열고 연필(편집) 버튼으로 한 줄에 하나씩 적습니다.
- 같은 날에는 한 번만 보냅니다. '지금 발행'을 다시 눌러도 두 번 가지 않습니다.
- 회사 메일은 처음에 스팸함으로 갈 수 있습니다. 첫 메일을 '스팸 아님'으로 표시하거나 보내는 주소를 주소록에 넣어 주세요.

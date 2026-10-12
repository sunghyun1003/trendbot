# 집 PC 설치 안내서

집 PC에서 할 일은 전부 이 문서에 있습니다. 회사 PC에는 아무것도 설치하지 않고, 완성된 사이트를 브라우저로 열기만 합니다. 윈도우 기준입니다.

**걸리는 시간:** 처음 한 번, 약 30분. 키 입력은 마지막에 한꺼번에 합니다.

---

## 1단계. 프로그램 3개 설치 (10분)

| 프로그램 | 받는 곳 | 주의할 점 |
|---|---|---|
| Python 3.12 이상 | https://www.python.org/downloads/ | 설치 첫 화면에서 **"Add python.exe to PATH" 체크** |
| Git | https://git-scm.com/download/win | 기본값 그대로 "Next" |
| Node.js LTS | https://nodejs.org/ | 기본값 그대로 |

## 2단계. 코드 받기 (2분)

시작 메뉴에서 **PowerShell**을 열고, 아래를 한 줄씩 붙여 넣습니다.

```powershell
cd $HOME
git clone https://github.com/sunghyun1003/trendbot.git
cd trendbot
git checkout claude/wizardly-edison-b339ub
```

브라우저 로그인 창이 뜨면 GitHub 계정으로 로그인합니다.

## 3단계. 원클릭 설치 (10분)

PowerShell을 **관리자 권한으로 실행**합니다(시작 메뉴 → PowerShell 우클릭 → 관리자 권한으로 실행). 그리고 아래를 붙여 넣습니다.

```powershell
cd $HOME\trendbot
powershell -ExecutionPolicy Bypass -File tools\setup_windows.ps1
```

이 스크립트가 다음을 자동으로 처리합니다.
- 전용 파이썬 환경 만들기와 필요한 패키지 설치
- 캡처·네이버 카페용 브라우저 설치
- `.env` 설정 파일 만들기(아직 빈칸)
- 자동 실행 일정 등록
- 전원 연결 시 절전 끄기
- 마지막에 점검 결과 출력

이 시점에는 키가 비어 있어서 점검 결과에 ✗가 보이는 것이 정상입니다.

> 아래부터는 `python` 대신 `.venv\Scripts\python.exe`를 씁니다. 길면 먼저 `.venv\Scripts\activate`를 한 번 실행하세요. 그러면 그 창에서는 `python`만 써도 됩니다.

## 4단계. 네이버 로그인 (3분)

```powershell
.venv\Scripts\python.exe -m trendbot naver-login
```

1. 열린 전용 브라우저 창에서 네이버에 **직접** 로그인합니다('로그인 상태 유지' 체크).
2. 디젤매니아 카페(https://cafe.naver.com/dieselmania)에 들어가 인기글이 보이는지 확인합니다.
3. 창을 닫습니다.

- 수집기는 비밀번호를 모르고, 자동 로그인도 하지 않습니다.
- 로그인이 풀리면 사이트 '상태' 화면에 표시되니, 이 단계만 다시 하면 됩니다.
- 평소 쓰는 주 계정 대신 **수집 전용 계정** 사용을 권장합니다.

## 5단계. 사이트 점검 1회 (10분)

```powershell
.venv\Scripts\python.exe -m trendbot probe
```

사이트마다 접속·차단 여부를 확인하고, 목록과 글 화면 샘플을 저장합니다. 끝나면 결과를 올립니다.

```powershell
git add -f data/probe_report.md tests/fixtures
git commit -m "집 PC 점검 결과"
git push
```

올린 뒤 Claude Code에 **"점검 결과 올렸어"** 라고 알려 주세요. 클라우드에서 막혔던 디시·인스티즈·더쿠·82쿡·디젤매니아를 이 결과로 맞춥니다.

## 6단계. 키 넣기 (마지막에 한꺼번에)

1. [키 발급 안내서](keys-guide.md)대로 키를 발급받습니다.
2. `trendbot` 폴더의 `.env` 파일을 메모장으로 열어 채웁니다.
3. 점검을 실행합니다.

```powershell
.venv\Scripts\python.exe -m trendbot doctor
```

모든 줄이 ✓(선택 항목은 –)이면 첫 발행을 해 봅니다.

```powershell
.venv\Scripts\python.exe -m trendbot snapshot --naver
.venv\Scripts\python.exe -m trendbot daily
```

첫 발행이 끝나면 **바로** [키 발급 안내서 3-4](keys-guide.md)대로 사이트를 잠급니다. 잠근 뒤 `doctor`를 다시 실행해 "잠금 ✓"를 확인하세요.

## 이후: 자동 운영

| 시각 | 하는 일 |
|---|---|
| 01:30, 12:00, 22:00 | 커뮤니티·검색·영상 수집 |
| 06:30, 17:00 | 위와 같음 + 네이버 카페 |
| 07:00 | 피드백 가져오기 → 오늘의 판 만들기 → 사이트 배포 (07:30 전 완료) |

- 실행할 때마다 최신 코드를 자동으로 받으니, 코드 업데이트를 따로 할 필요는 없습니다.
- 윈도우 업데이트는 설정 → Windows 업데이트 → 고급 옵션 → **사용 시간**을 새벽 1~7시가 아닌 시간으로 잡아, 수집 시간에 재부팅되지 않게 합니다.

## 문제가 생겼을 때

| 증상 | 할 일 |
|---|---|
| 무엇이 문제인지 모르겠음 | `.venv\Scripts\python.exe -m trendbot doctor` → ✗ 줄의 → 안내대로 |
| 사이트 '상태'에 모든 소스가 고장 | 집 PC가 꺼졌거나 인터넷이 끊김 → PC 켜기 |
| "네이버 로그인 필요" | 4단계 다시 |
| 한 사이트만 고장 | Claude Code에 "고장 수리: (사이트 이름)" |
| 실행 기록 보기 | `data\logs\run.log` |

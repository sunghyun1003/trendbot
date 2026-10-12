# ㄷㅅㅂㄱ 집 PC 원클릭 설치
# 사용법: 저장소 폴더에서 PowerShell을 '관리자 권한으로' 열고
#   powershell -ExecutionPolicy Bypass -File tools\setup_windows.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Step($msg) { Write-Host "`n▶ $msg" -ForegroundColor Cyan }
function Done($msg) { Write-Host "  ✓ $msg" -ForegroundColor Green }
function Warn($msg) { Write-Host "  ! $msg" -ForegroundColor Yellow }

Step "1/6 프로그램 확인"
foreach ($cmd in @("python", "git", "npx")) {
  if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
    Warn "$cmd 이(가) 없습니다. docs\setup-home-pc.md 1단계대로 설치한 뒤 다시 실행하세요."
    exit 1
  }
}
Done "python, git, node 확인"

Step "2/6 전용 파이썬 환경(.venv) 만들기"
if (-not (Test-Path ".venv")) { python -m venv .venv }
& .venv\Scripts\python.exe -m pip install --upgrade pip -q
& .venv\Scripts\python.exe -m pip install -r requirements-home.txt -q
Done "패키지 설치"

Step "3/6 캡처·네이버 카페용 브라우저 설치"
& .venv\Scripts\python.exe -m playwright install chromium
Done "브라우저 설치"

Step "4/6 설정 파일(.env) 준비"
if (-not (Test-Path ".env")) {
  Copy-Item ".env.example" ".env"
  Done ".env 를 만들었습니다. 마지막에 docs\keys-guide.md 를 보고 키를 채우세요."
} else { Done ".env 가 이미 있습니다" }

Step "5/6 자동 실행 일정 등록"
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if ($isAdmin) {
  & powershell -ExecutionPolicy Bypass -File "$root\tools\install_schedule.ps1"
  Done "일정 등록"
} else {
  Warn "관리자 권한이 아니라 일정 등록을 건너뜁니다. PowerShell을 '관리자 권한으로 실행'해서 이 스크립트를 다시 돌리세요."
}
powercfg /change standby-timeout-ac 0 | Out-Null
Done "전원 연결 시 절전 모드: 안 함"

Step "6/6 점검"
& .venv\Scripts\python.exe -m trendbot doctor --quick
Write-Host "`n다음 할 일:" -ForegroundColor Cyan
Write-Host "  1) 네이버 로그인:   .venv\Scripts\python.exe -m trendbot naver-login"
Write-Host "  2) 사이트 점검:     .venv\Scripts\python.exe -m trendbot probe   (결과는 안내서대로 올리기)"
Write-Host "  3) 키 넣기:         docs\keys-guide.md 를 보고 .env 채운 뒤  .venv\Scripts\python.exe -m trendbot doctor"

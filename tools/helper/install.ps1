# ㄷㅅㅂㄱ 집 PC 도우미 설치 (대시보드에서 받은 dsbg-setup.cmd 가 자동으로 실행합니다)
# 관리자 권한 필요 없음. 모든 파일은 %LOCALAPPDATA%\dsbg 한 폴더에만 들어갑니다.
param([Parameter(Mandatory)][string]$Token, [Parameter(Mandatory)][string]$Site)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'   # 내려받기 속도가 훨씬 빨라짐
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$Base = Join-Path $env:LOCALAPPDATA 'dsbg'
$Py = Join-Path $Base 'python'
$App = Join-Path $Base 'app'
$PyVer = '3.12.10'
$Headers = @{ 'X-Agent-Token' = $Token }

function Step($n, $msg) { Write-Host ""; Write-Host "[$n/7] $msg" -ForegroundColor Cyan }
function Fail($msg) {
  Write-Host ""; Write-Host "설치가 멈췄습니다: $msg" -ForegroundColor Red
  Write-Host "인터넷 연결을 확인하고 dsbg-setup.cmd 를 다시 더블클릭해 주세요. 계속 안 되면 이 창을 캡처해 Claude에게 보여 주세요."
  exit 1
}

try {
  Step 1 '폴더 준비'
  New-Item -ItemType Directory -Force -Path $Base, $App | Out-Null
  @{ token = $Token; site = $Site } | ConvertTo-Json | Set-Content -Encoding UTF8 (Join-Path $Base 'config.json')

  Step 2 '실행 엔진 내려받기 (약 10MB, 사용자에게는 보이지 않음)'
  if (-not (Test-Path (Join-Path $Py 'python.exe'))) {
    $zip = Join-Path $env:TEMP 'dsbg-python.zip'
    Invoke-WebRequest -UseBasicParsing "https://www.python.org/ftp/python/$PyVer/python-$PyVer-embed-amd64.zip" -OutFile $zip
    Expand-Archive -Force $zip $Py
    $pth = Get-ChildItem $Py -Filter 'python*._pth' | Select-Object -First 1
    (Get-Content $pth.FullName) -replace '^#\s*import site', 'import site' | Set-Content $pth.FullName
    Add-Content $pth.FullName '..\app'
    Invoke-WebRequest -UseBasicParsing 'https://bootstrap.pypa.io/get-pip.py' -OutFile (Join-Path $Py 'get-pip.py')
    & (Join-Path $Py 'python.exe') (Join-Path $Py 'get-pip.py') --no-warn-script-location -q
    if ($LASTEXITCODE -ne 0) { Fail '실행 엔진 준비 실패' }
  }

  Step 3 '부품 설치 (2~3분)'
  & (Join-Path $Py 'python.exe') -m pip install -q --no-warn-script-location --upgrade httpx beautifulsoup4 pyyaml pillow playwright
  if ($LASTEXITCODE -ne 0) { Fail '부품 설치 실패' }

  Step 4 '도우미 프로그램 받기'
  $code = Join-Path $env:TEMP 'dsbg-app.zip'
  Invoke-WebRequest -UseBasicParsing -Headers $Headers "$Site/api/agent?get=code" -OutFile $code
  Expand-Archive -Force $code $App

  Step 5 '바탕화면에 네이버 로그인 아이콘 만들기'
  $pyw = Join-Path $Py 'pythonw.exe'
  $lnk = (New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path ([Environment]::GetFolderPath('Desktop')) 'ㄷㅅㅂㄱ 네이버 로그인.lnk'))
  $lnk.TargetPath = $pyw
  $lnk.Arguments = "`"$(Join-Path $App 'helper.py')`" login"
  $lnk.WorkingDirectory = $App
  $lnk.IconLocation = 'msedge.exe,0'
  $lnk.Save()

  Step 6 '30분마다 자동 실행 등록 (PC를 켜 두기만 하면 됨)'
  $action = New-ScheduledTaskAction -Execute $pyw -Argument "`"$(Join-Path $App 'helper.py')`" run" -WorkingDirectory $App
  $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 30) -RepetitionDuration (New-TimeSpan -Days 3650)
  $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 1) -MultipleInstances IgnoreNew
  Register-ScheduledTask -TaskName 'dsbg-helper' -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
  try { powercfg /change standby-timeout-ac 0 | Out-Null } catch { }   # 전원 연결 시 절전 끄기

  Step 7 '네이버 로그인 창 열기'
  Write-Host '잠시 후 열리는 Edge 창에서 네이버에 직접 로그인하고(로그인 상태 유지 체크), 창을 닫아 주세요.' -ForegroundColor Yellow
  Start-Process -FilePath $pyw -ArgumentList "`"$(Join-Path $App 'helper.py')`" login" -WorkingDirectory $App

  Write-Host ""; Write-Host '설치 완료! 이제 PC를 켜 두기만 하면 됩니다. 이 창은 닫아도 됩니다.' -ForegroundColor Green
} catch {
  Fail $_.Exception.Message
}

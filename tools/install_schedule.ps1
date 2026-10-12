# 윈도우 작업 스케줄러에 수집·발행 일정을 등록합니다. (PowerShell을 관리자 권한으로 실행)
$root = Split-Path -Parent $PSScriptRoot
$bat = Join-Path $root "tools\run.bat"
$settings = New-ScheduledTaskSettingsSet -WakeToRun -StartWhenAvailable -DontStopIfGoingOnBatteries -AllowStartIfOnBatteries

function Add-Job($name, $time, $args) {
  $action = New-ScheduledTaskAction -Execute $bat -Argument $args -WorkingDirectory $root
  $trigger = New-ScheduledTaskTrigger -Daily -At $time
  Register-ScheduledTask -TaskName "trendbot-$name" -Action $action -Trigger $trigger -Settings $settings -Force | Out-Null
  Write-Host "등록: trendbot-$name ($time)"
}

Add-Job "snap-0130" "01:30" "snapshot"
Add-Job "snap-0630" "06:30" "snapshot --naver"
Add-Job "daily-0700" "07:00" "daily"
Add-Job "snap-1200" "12:00" "snapshot"
Add-Job "snap-1700" "17:00" "snapshot --naver"
Add-Job "snap-2200" "22:00" "snapshot"
Write-Host "완료. '작업 스케줄러' 앱에서 trendbot-로 시작하는 작업 6개를 확인할 수 있습니다."

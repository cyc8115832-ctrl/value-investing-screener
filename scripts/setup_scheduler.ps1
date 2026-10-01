param(
    [ValidateSet("Install", "Status", "Uninstall", "TestRun")]
    [string]$Action = "Status"
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host " Value Investing Screener - Windows Task Scheduler Tool" -ForegroundColor Cyan
Write-Host " Project Directory: $ProjectRoot" -ForegroundColor Gray
Write-Host " Python Executable: $VenvPython" -ForegroundColor Gray
Write-Host " Action: $Action" -ForegroundColor Yellow
Write-Host "========================================================" -ForegroundColor Cyan

if (-not (Test-Path $VenvPython)) {
    Write-Host "[ERROR] Cannot find virtualenv Python: $VenvPython" -ForegroundColor Red
    Write-Host "Please run: python -m venv .venv in the project root." -ForegroundColor Yellow
    exit 1
}

$TaskPipelineName = "ValueInvesting_DailyPipeline_1530"
$TaskBackupName   = "ValueInvesting_DatabaseBackup_0300"
$TaskHealthName   = "ValueInvesting_MorningHealth_0830"

$ScriptPipeline = Join-Path $ProjectRoot "scripts\daily_pipeline.py"
$ScriptBackup   = Join-Path $ProjectRoot "scripts\backup_db.py"
$ScriptHealth   = Join-Path $ProjectRoot "scripts\health_check.py"

if ($Action -eq "Install") {
    Write-Host "`nRegistering scheduled tasks to Windows Task Scheduler..." -ForegroundColor Green

    # 1. 盤後重算任務 (週一至週五 15:30)
    $ActionPipeline = New-ScheduledTaskAction -Execute $VenvPython -Argument "`"$ScriptPipeline`" --push" -WorkingDirectory $ProjectRoot
    $TriggerPipeline = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At 15:30
    Register-ScheduledTask -TaskName $TaskPipelineName -Action $ActionPipeline -Trigger $TriggerPipeline -Description "價值投資選股 App - 盤後 15:30 自動重算管線與 LINE 推播" -Force | Out-Null
    Write-Host "  [OK] Registered: $TaskPipelineName (Mon-Fri 15:30)" -ForegroundColor Green

    # 2. 資料庫熱備份任務 (每日 03:00)
    $ActionBackup = New-ScheduledTaskAction -Execute $VenvPython -Argument "`"$ScriptBackup`" --keep-days 14" -WorkingDirectory $ProjectRoot
    $TriggerBackup = New-ScheduledTaskTrigger -Daily -At 03:00
    Register-ScheduledTask -TaskName $TaskBackupName -Action $ActionBackup -Trigger $TriggerBackup -Description "價值投資選股 App - 每日 03:00 SQLite 安全熱備份與過期清理" -Force | Out-Null
    Write-Host "  [OK] Registered: $TaskBackupName (Daily 03:00)" -ForegroundColor Green

    # 3. 開盤前自檢任務 (週一至週五 08:30)
    $ActionHealth = New-ScheduledTaskAction -Execute $VenvPython -Argument "`"$ScriptHealth`"" -WorkingDirectory $ProjectRoot
    $TriggerHealth = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday,Tuesday,Wednesday,Thursday,Friday -At 08:30
    Register-ScheduledTask -TaskName $TaskHealthName -Action $ActionHealth -Trigger $TriggerHealth -Description "價值投資選股 App - 開盤前 08:30 系統健康自檢" -Force | Out-Null
    Write-Host "  [OK] Registered: $TaskHealthName (Mon-Fri 08:30)" -ForegroundColor Green

    Write-Host "`nAll scheduled tasks registered successfully!" -ForegroundColor Cyan

} elseif ($Action -eq "Uninstall") {
    Write-Host "`nRemoving scheduled tasks..." -ForegroundColor Yellow
    foreach ($tname in @($TaskPipelineName, $TaskBackupName, $TaskHealthName)) {
        if (Get-ScheduledTask -TaskName $tname -ErrorAction SilentlyContinue) {
            Unregister-ScheduledTask -TaskName $tname -Confirm:$false
            Write-Host "  [Removed] $tname" -ForegroundColor Yellow
        } else {
            Write-Host "  [Not Found] $tname" -ForegroundColor Gray
        }
    }
    Write-Host "`nTasks removed successfully." -ForegroundColor Green

} elseif ($Action -eq "Status") {
    Write-Host "`nCurrent Task Scheduler Status:" -ForegroundColor White
    foreach ($tname in @($TaskPipelineName, $TaskBackupName, $TaskHealthName)) {
        $task = Get-ScheduledTask -TaskName $tname -ErrorAction SilentlyContinue
        if ($task) {
            $info = Get-ScheduledTaskInfo -TaskName $tname -ErrorAction SilentlyContinue
            Write-Host "  [Active] $tname" -ForegroundColor Green
            Write-Host "     State: $($task.State)" -ForegroundColor Gray
            Write-Host "     LastRun: $($info.LastRunTime)" -ForegroundColor Gray
            Write-Host "     NextRun: $($info.NextRunTime)" -ForegroundColor Gray
        } else {
            Write-Host "  [Inactive] $tname (Not installed)" -ForegroundColor DarkGray
        }
    }
    Write-Host "`nTo install tasks, run: .\scripts\setup_scheduler.ps1 -Action Install" -ForegroundColor Yellow

} elseif ($Action -eq "TestRun") {
    Write-Host "`nRunning test health check and backup..." -ForegroundColor Cyan
    & $VenvPython $ScriptHealth
    Write-Host ""
    & $VenvPython $ScriptBackup --keep-days 7
}

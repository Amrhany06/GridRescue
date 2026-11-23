# Approved official WSL bootstrap. Never restarts Windows or edits project data.
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$reportPath = Join-Path $projectRoot 'reports/wsl_installation.json'
$report = [ordered]@{ started_utc = [DateTime]::UtcNow.ToString('o'); status = 'RUNNING'; automatic_reboot = $false; commands = @() }
try {
    $admin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    if (-not $admin) { throw 'Administrator elevation is required for the approved WSL installation.' }
    foreach ($wslArgs in @(@('--install','--no-distribution'), @('--install','--distribution','Ubuntu-24.04','--no-launch'))) {
        $result = & "$env:WINDIR\System32\wsl.exe" @wslArgs 2>&1
        $commandExit = $LASTEXITCODE
        $message = (($result | Out-String) -replace "`0", '')
        $report.commands += [ordered]@{ arguments = $wslArgs; exit_code = $commandExit; output = $message }
        if ($commandExit -eq 3010 -or $message -match '(?i)restart.*required|reboot.*required|reboot.*take effect|restart.*take effect') {
            $report.status = 'MANUAL_RESTART_REQUIRED'
            break
        }
        if ($commandExit -ne 0) { throw "Official WSL command failed with exit code $commandExit. Inspect recorded output." }
    }
    if ($report.status -eq 'RUNNING') { $report.status = 'INSTALL_COMMANDS_COMPLETED; LINUX_EXECUTION_NOT_YET_VERIFIED' }
} catch {
    $report.status = 'FAILED'
    $report.error = $_.Exception.Message
} finally {
    $report.completed_utc = [DateTime]::UtcNow.ToString('o')
    $report | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $reportPath -Encoding UTF8
}
if ($report.status -eq 'FAILED') { exit 1 }

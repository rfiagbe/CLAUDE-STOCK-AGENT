# Morning picks at a fixed 9:00 AM ET, fired by Windows Task Scheduler
# ("Daily Stock Picks"). GitHub's schedule trigger runs hours late, so the
# on-time email comes from here; the GitHub workflow is only a fallback and
# skips any day this script has already sent.
#
#   powershell -File run_morning.ps1           # pull, screen, email, push
#   powershell -File run_morning.ps1 -DryRun   # pull + screen only, no email/CSV/push

param([switch]$DryRun)

Set-Location $PSScriptRoot
$env:PYTHONUTF8 = '1'
$python = 'C:\Users\fiagb\AppData\Local\Python\pythoncore-3.14-64\python.exe'
$logFile = Join-Path $PSScriptRoot 'task_run.log'

function Log([string]$msg) {
    "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') [morning] $msg" | Out-File -FilePath $logFile -Append -Encoding utf8
}

Log "start (DryRun=$DryRun)"

git pull --rebase origin main 2>&1 | ForEach-Object { Log "git: $_" }

$today = Get-Date -Format 'yyyy-MM-dd'
if (-not $DryRun -and (Import-Csv picks_history.csv | Where-Object { $_.date -eq $today })) {
    Log "picks for $today already recorded; skipping"
    exit 0
}

$agentArgs = @('stock_agent.py')
if ($DryRun) { $agentArgs += '--dry-run' }
& $python @agentArgs 2>&1 | ForEach-Object { Log "$_" }
$code = $LASTEXITCODE
if ($code -ne 0) { Log "stock_agent.py exited $code"; exit $code }
if ($DryRun) { Log 'dry run complete'; exit 0 }

git add picks_history.csv benchmark_history.csv dashboard.html index.html
git diff --cached --quiet
if ($LASTEXITCODE -ne 0) {
    git commit -m "Morning picks $today (9:00 AM ET local)" 2>&1 | ForEach-Object { Log "git: $_" }
    for ($i = 1; $i -le 3; $i++) {
        git pull --rebase origin main 2>&1 | ForEach-Object { Log "git: $_" }
        git push origin main 2>&1 | ForEach-Object { Log "git: $_" }
        if ($LASTEXITCODE -eq 0) { break }
        Log "push attempt $i failed; retrying in 20s"
        Start-Sleep -Seconds 20
    }
}
Log 'done'

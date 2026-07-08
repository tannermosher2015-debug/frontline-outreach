#requires -Version 5.1
<#
  Register the Frontline Outreach funnel on THIS machine.
  One task:
    FrontlineOutreach-Daily  (07:30)  run  (discover + audit + score + draft, saves leads)
  DISCOVERY ONLY. The cold-email send loop (send / send-followups / replies / send-samples)
  is intentionally NOT scheduled: measured 2026-07-07, only 1 of 70 Maui leads had a
  reachable email, so cold email is a dead channel for this segment. Discovery still runs
  because it feeds the phone call sheet (`python -m outreach queue` / call-sheet.csv), which
  is the live channel (60 of 70 have a phone). To re-enable email, add the send actions back.

  Install:  powershell -ExecutionPolicy Bypass -File .\schedule.ps1
  Remove:   powershell -ExecutionPolicy Bypass -File .\schedule.ps1 -Remove

  Tasks run only while this machine is on and the user is logged in.
#>
param([switch]$Remove)

$repo   = $PSScriptRoot
$py     = Join-Path $repo '.venv\Scripts\python.exe'
$prefix = 'FrontlineOutreach-'

# Clear existing tasks first (idempotent; also handles -Remove).
Get-ScheduledTask -TaskName "$prefix*" -ErrorAction SilentlyContinue |
    Unregister-ScheduledTask -Confirm:$false
if ($Remove) { Write-Host 'Removed Frontline Outreach tasks.'; return }

if (-not (Test-Path $py)) {
    Write-Error "venv python not found at $py. First run:  python -m venv .venv;  .\.venv\Scripts\pip install -e '.[dev]'"
    return
}

$set = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew

# Daily: discover + audit + score + draft today's leads (no sending). Feeds the call sheet.
$daily = @(
    New-ScheduledTaskAction -Execute $py -Argument '-m outreach run' -WorkingDirectory $repo
)
Register-ScheduledTask -TaskName "${prefix}Daily" -Action $daily -Settings $set `
    -Trigger (New-ScheduledTaskTrigger -Daily -At ([datetime]'07:30')) `
    -Description 'Frontline Outreach: discover + score the daily lead batch (no send)' | Out-Null

Write-Host "Registered ${prefix}Daily (07:30): discovery only, no email sending."
Write-Host 'Cold email is disabled on purpose (dead channel for this segment; see header).'
Write-Host 'Work the leads by phone:  python -m outreach queue   (or call-sheet.csv)'

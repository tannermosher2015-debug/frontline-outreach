#requires -Version 5.1
<#
  Register the Frontline Outreach funnel as scheduled tasks on THIS machine.
  Two tasks:
    FrontlineOutreach-Daily  (07:30)          run + send + send-followups  (build leads, cold email, nudges)
    FrontlineOutreach-Poll   (08:00, every 2h) replies + send-samples (read replies, send ready samples)
  Both respect send_mode in config.toml (dry_run until you flip it to live).
  Stage 4 (auto-build demos) is a Claude agent and is NOT scheduled here; see the note below.

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

# Daily: build today's leads, then send the cold batch.
$daily = @(
    New-ScheduledTaskAction -Execute $py -Argument '-m outreach run'            -WorkingDirectory $repo
    New-ScheduledTaskAction -Execute $py -Argument '-m outreach send'           -WorkingDirectory $repo
    New-ScheduledTaskAction -Execute $py -Argument '-m outreach send-followups' -WorkingDirectory $repo
)
Register-ScheduledTask -TaskName "${prefix}Daily" -Action $daily -Settings $set `
    -Trigger (New-ScheduledTaskTrigger -Daily -At ([datetime]'07:30')) `
    -Description 'Frontline Outreach: build + send the daily cold batch' | Out-Null

# Poll: read replies, then send any ready samples, every 2h across the day.
$poll = @(
    New-ScheduledTaskAction -Execute $py -Argument '-m outreach replies'      -WorkingDirectory $repo
    New-ScheduledTaskAction -Execute $py -Argument '-m outreach send-samples' -WorkingDirectory $repo
)
$pollTrigger = New-ScheduledTaskTrigger -Once -At ([datetime]'08:00') `
    -RepetitionInterval (New-TimeSpan -Hours 2) -RepetitionDuration (New-TimeSpan -Hours 12)
Register-ScheduledTask -TaskName "${prefix}Poll" -Action $poll -Settings $set `
    -Trigger $pollTrigger -Description 'Frontline Outreach: read replies + send ready samples' | Out-Null

Write-Host "Registered ${prefix}Daily (07:30) and ${prefix}Poll (every 2h, 08:00-20:00)."
Write-Host 'They run in whatever send_mode config.toml is set to (currently dry_run).'
Write-Host ''
Write-Host 'Stage 4 (auto-build demos) is a Claude agent, not scheduled here. To automate it,'
Write-Host 'add a task on a machine with Claude Code that runs, in this repo:'
Write-Host '   claude -p "Follow BUILD_QUEUE.md and work the build queue."'

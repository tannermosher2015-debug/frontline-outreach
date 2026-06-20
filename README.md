# Frontline Outreach

Daily local-business lead-gen tool for Frontline Web Designs. Discovers Maui
businesses with weak web presence, audits what they're missing, scores by
opportunity, drafts outreach in Tanner's voice, and lets you review/send from a
local dashboard. Auto-email is **dry-run by default**.

## Setup (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
copy .env.example .env   # then fill in PLACES_API_KEY and RESEND_API_KEY
```

## Daily use

```powershell
python -m outreach run      # build today's 10 leads
python -m outreach serve    # open the dashboard, review + send
```

DMs are copy-paste from the dashboard (Instagram/Facebook automation is against
their ToS). Email auto-send stays in dry-run (writes outbox/*.eml) until you set
`send_mode = "live"` in config.toml with Resend + frontlinewebdesign.tech.

## Test

```powershell
pytest -q
```

## Config

Edit `config.toml`: target towns/categories, scoring weights, `daily_email_cap`,
`send_mode`, provider. Secrets live in `.env` (never committed).

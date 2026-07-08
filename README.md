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
`send_mode = "live"` in config.toml.

## Autonomous funnel

The full loop, cold email to paid deposit, runs as "Maui Web Guy" through the Hostinger
mailbox tanner@mauiwebguy.com (config: `provider = "smtp"`, from/reply on mauiwebguy.com;
`.env` holds SMTP_* and IMAP_* for that mailbox).

```powershell
python -m outreach run            # discover + audit + score + draft today's leads
python -m outreach send           # cold email (free-sample offer), capped, dry-run first
python -m outreach replies        # read inbox, sort replies: yes -> interested, no -> suppressed
python -m outreach queue          # interested leads still needing a sample built
python -m outreach set-sample <place_id> <url>   # record a built demo URL
python -m outreach send-samples   # email the demo + $150 deposit link to interested leads
python -m outreach send-followups # one gentle nudge to non-repliers, within the daily cap
```

Stage 4 (auto-build a demo per interested lead) is a Claude agent, see `BUILD_QUEUE.md`.
`schedule.ps1` registers Windows Task Scheduler jobs (Daily: run + send + send-followups;
Poll every 2h: replies + send-samples). Everything respects `send_mode` (dry_run by default).

### Going live
1. Rotate the mailbox password if it was ever exposed, and update `.env`.
2. `python -m outreach run`, then `python -m outreach send`, and read `outbox/*.eml`.
3. Set `send_mode = "live"`. Cold email goes out at `daily_email_cap`/day (start at 3 to warm
   a new sending domain, ramp toward 10).

## Test

```powershell
pytest -q
```

## Config

Edit `config.toml`: target towns/categories, scoring weights, `daily_email_cap`,
`send_mode`, provider. Secrets live in `.env` (never committed).

## Social lookup (optional)

For no-website leads, the tool can find the business's Instagram/Facebook handle via
Google's Custom Search JSON API and show it in the dashboard (DMs stay manual).

1. Google Cloud -> enable **Custom Search API** (can reuse your Places project/key).
2. Create a **Programmable Search Engine** that searches the entire web -> copy its **CX** id.
3. Add to `.env`:
   ```
   GOOGLE_CSE_KEY=your-key
   GOOGLE_CSE_CX=your-cx-id
   ```
4. In `config.toml`, keep `[socials] enabled = true`.

Free for 100 searches/day (the run uses at most one per social lead, capped at your
`batch_size`). Set `enabled = false` to turn it off — the tool runs fine without it.

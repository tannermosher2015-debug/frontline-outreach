# Frontline Outreach — Design Spec

- **Date:** 2026-06-19
- **Owner:** Tanner / Frontline Web Designs
- **Status:** Approved design, pre-implementation
- **Repo (canonical):** `C:\Users\Tanne\frontline-outreach` (outside OneDrive per machine rule)

## 1. Goal

A local tool that runs daily, **discovers** local businesses with weak or missing web
presence, **audits** what each one is lacking, **scores** them by opportunity, **drafts** a
personalized outreach message in Tanner's voice, and lets him review + send from a local
dashboard — never re-surfacing a business he has already contacted.

End-state goal is **automated email outreach** (find → audit → auto-send the right message
based on what the business is missing). This is built in from day one but ships **dry-run by
default** with the dashboard as the approval gate, so nothing goes out under Tanner's name
until he has seen it work and flipped it live.

## 2. Users & context

- Single user (Tanner), running on his laptop and PC (both sync via git remotes).
- Windows 11, PowerShell, Python. `gh` not installed; git over SSH.
- Market: Maui / Hawaii small businesses. Pitch identity: *local Maui firefighter who builds
  clean, mobile-friendly sites on the side; free website sample upon request.*
- Internal tool — **no auto-deploy**, runs only on Tanner's machines. Secrets never committed.

## 3. Scope

### In scope (v1, build now)
- Auto-discovery via **Google Places API (New)** for a configurable list of Maui towns × business categories.
- Per-business **audit** of the 8 weak-presence signals.
- **Opportunity scoring** + plain-English problem summary.
- **Per-lead channel selection** (email → DM → phone) and **template-based drafting** in Tanner's voice.
- **Local Flask dashboard** (SQLite-backed) to review, edit, mark contacted/skip, and approve sends.
- **`send.py`** automated email sending — **dry-run by default**, Resend + `frontlinewebdesign.tech` when live, with caps + compliance + dedup.
- A persistent **never-repeat ledger** so each business is surfaced/contacted at most once.

### Out of scope (deliberate)
- **Automated Instagram/Facebook DM sending** — against platform ToS, account-ban risk. DMs are copy-paste from the dashboard, always manual.
- Fully unattended cron send (no human in the loop). The toggle exists but stays off until trusted.
- A hosted/multi-user web app. This is a personal, single-machine tool.
- True rendered mobile checks and photo-freshness CV in v1 (see Limitations + Phase 2).

## 4. Architecture

Python engine + thin Flask server + SQLite ledger. Each module has one job and is testable in isolation.

| Module | Responsibility | Depends on |
|---|---|---|
| `config.toml` | Towns, categories, batch size (10), scoring weights, send caps, mode flags. | — |
| `.env` (gitignored) | `PLACES_API_KEY`, `RESEND_API_KEY`, optional SMTP creds. Read via env vars. | — |
| `discover.py` | Query Places API for candidates per town × category. Returns raw business records. | Places API |
| `audit.py` | Pure function: business → findings object (the 8 signals). Fetches the site, parses HTML. | `requests`, `bs4` |
| `score.py` | Findings → 0–100 opportunity score + summary string. Pure. | config |
| `draft.py` | Pick channel + select/fill template → draft text. Pure. | templates, config |
| `store.py` | All SQLite reads/writes (the only DB-touching module). Dedup lives here. | sqlite3 |
| `pipeline.py` | Orchestrates: discover → drop already-seen → audit → score → top 10 → draft → save. | all above |
| `send.py` | Render + (dry-run or live) send email leads. Caps, compliance, suppression, logging. | Resend/SMTP, store |
| `server.py` | Flask: serve dashboard, handle status/approve/send POSTs. | store, send |
| `templates/`, `static/` | Jinja2 dashboard + outreach message templates. | — |
| `__main__.py` | CLI: `run`, `serve`, `send`. | pipeline, server, send |

### Data flow (daily)
```
run → discover(town×category) → store.filter_unseen()
    → audit() each → score() each → rank, take top 10 not in ledger
    → draft() each → store.save_batch(today)
serve → dashboard reads today's batch from SQLite
      → user edits / approves / skips → POST → store update (+ optional send.py)
```

## 5. Data model (SQLite)

```sql
businesses (
  place_id      TEXT PRIMARY KEY,   -- Google Places id; the never-repeat key
  name          TEXT,
  category      TEXT,
  town          TEXT,
  address       TEXT,
  phone         TEXT,
  website       TEXT,               -- null if none; may be an IG/FB url
  email         TEXT,               -- scraped if found
  rating        REAL,
  review_count  INTEGER,
  status        TEXT,               -- new | contacted | skipped | replied | client | dead
  first_seen    TEXT                -- ISO date
)

audits (
  id          INTEGER PRIMARY KEY,
  business_id TEXT REFERENCES businesses(place_id),
  run_date    TEXT,
  findings    TEXT,                 -- JSON: {signal: bool/detail}
  score       INTEGER,
  summary     TEXT
)

outreach (
  id           INTEGER PRIMARY KEY,
  business_id  TEXT REFERENCES businesses(place_id),
  channel      TEXT,                -- email | dm | phone
  draft_text   TEXT,               -- editable; final text used
  subject      TEXT,               -- email only
  created_at   TEXT,
  contacted_at TEXT,               -- null until confirmed sent/marked
  send_status  TEXT                 -- pending | dry_run | sent | send_failed | manual
)

suppression (
  email      TEXT PRIMARY KEY,      -- opt-outs / do-not-contact
  reason     TEXT,
  added_at   TEXT
)
```

`businesses` is the system of record for never-repeat. A re-run that re-discovers a known
`place_id` is dropped before auditing.

## 6. The weak-presence signals (audit)

The 8 target criteria, with "old photos or broken links" split into two separate checks → 9
detections. `audit.py` returns a findings object. Reliability is stated honestly — strong/good
signals drive the score; fuzzy ones are flagged for human review, not trusted blindly.

| Signal | Detection | Reliability |
|---|---|---|
| `no_website` | Places returns no `websiteUri` | strong |
| `social_only` | No real site, or `websiteUri` host is instagram.com / facebook.com | strong |
| `weak_google` | `userRatingCount` < threshold (default 15) and/or low `rating` | strong |
| `no_contact_button` | Fetched site has no `tel:`, no `mailto:`, no Contact link/form | good |
| `no_service_pages` | Nav/sitemap lacks service/menu/offerings pages; single thin page | good/heuristic |
| `outdated_website` | No `<meta viewport>`, stale footer copyright (≤ year−3), deprecated tags (`<font>`/`<center>`), no HTTPS, jQuery 1.x | heuristic |
| `bad_mobile` | No responsive viewport / fixed-width layout (static-HTML heuristic) | heuristic |
| `broken_links` | Sample internal+external links, HEAD-check for 404s (capped count) | good |
| `old_photos` | Stale image `Last-Modified` / filename dates | best-effort, flag for human |

If the site is unreachable/times out, that is recorded as its own strong signal (a broken or
dead site is a hot lead), not an error.

## 7. Scoring (`score.py`)

Each fired signal has a weight in `config.toml` (defaults below; all tunable):

```
no_website 30 · social_only 25 · outdated_website 20 · bad_mobile 20
no_contact_button 15 · weak_google 15 · no_service_pages 10
broken_links 10 · old_photos 5
```

`raw = sum(weights of fired signals)`; `score = min(100, raw)` (higher = hotter lead).
Businesses with Places `businessStatus != OPERATIONAL` are filtered out (don't pitch closed
shops). Output includes a human summary, e.g. *"No mobile layout · no contact button · last
updated 2018."* Candidates are ranked by score; the top 10 not already in the ledger become
today's batch.

## 8. Drafting (`draft.py`)

**Channel selection (priority):** scraped public **email** → **IG/FB DM** (profile known) →
**phone** (number known) → else flag "no contact found."

**Template matrix** keyed on `(channel × primary_problem)`, where `primary_problem` is the
highest-weighted fired signal. Templates inject the business name + the 1–2 specific findings
and end on the **free-sample CTA**. Tanner's verbatim scripts are the canonical base.

### Canonical scripts (DM voice — verbatim)

**No website:**
> Aloha, my name is Tanner with Frontline Web Designs. I'm a local Maui firefighter and I build
> clean websites for small businesses on the side. I came across your business and noticed you
> may not have a dedicated website yet. I'm currently offering a free website sample upon request,
> so you can see what your business could look like online before committing to anything. Would
> you like me to put together a sample for you?

**Outdated website:**
> Aloha, my name is Tanner with Frontline Web Designs. I'm a local Maui firefighter and I build
> clean, mobile-friendly websites for small businesses. I checked out your current website and I
> think I could help make it look more modern, easier to use, and better at getting customers to
> contact you. I'm offering a free website sample upon request if you'd like to see what a cleaner
> version could look like.

**Instagram/Facebook-only:**
> Aloha, my name is Tanner with Frontline Web Designs. I'm a local Maui firefighter helping small
> businesses build clean, professional websites. Your Instagram looks solid, but having a website
> can make it easier for customers to find your services, prices, photos, contact info, and book
> with you. I'm offering a free website sample upon request if you'd like to see what your business
> could look like online.

### To author during build (in the same voice)
- Conditions: `weak_google`, `no_contact_button`, plus a generic fallback.
- **Email versions** of every script, each with a **subject line** (the automation target is email).

## 9. Sending (`send.py`)

- **Dry-run by default:** renders each email to `outbox/*.eml` + logs it; sends nothing. Tanner
  inspects, then sets `mode = "live"` in config.
- **Live provider:** **Resend**, sending from **frontlinewebdesign.tech** (SPF/DKIM configured
  once) for cold-outreach deliverability and to protect the personal Gmail reputation. **Gmail
  SMTP (app password)** remains a fallback for testing.
- **Caps & dedup:** ≤10 emails/day (config), **one email per business ever**, spacing between
  sends. Checks the ledger; never double-sends.
- **Compliance (CAN-SPAM):** every email includes Tanner's real name + Frontline + a one-line
  opt-out ("reply 'not interested' and I won't follow up") and honors the `suppression` list.
- **Approval gate:** even in live mode, default is **per-lead Approve & Send** in the dashboard.
  Unattended send is a separate, off-by-default toggle.
- A send failure marks the lead `send_failed` (stays in queue, shown in dashboard); a lead is
  only marked `contacted` on a confirmed send.

## 10. Dashboard (`server.py` + templates)

- **Today view:** the 10 leads as cards — name · category · town, opportunity-score badge,
  problem chips, contact + detected channel, and the **editable draft** (edits persist to
  `outreach.draft_text` before any send).
- **Per-card actions by channel:**
  - Email → `Approve & Send`, `Copy`, `Skip`
  - DM → `Copy DM`, `Open Instagram/FB`, `Mark contacted`
  - Phone → number + script, `Mark called`
- **History view:** everyone contacted, with date + channel + status.
- Status changes POST to Flask → SQLite; pills update live. Accessible markup (labels, focus
  states, semantic landmarks) per Frontline standards.

## 11. Config, secrets & ops

- `config.toml`: `towns`, `categories`, `batch_size = 10`, `weights`, `weak_google_threshold`,
  `daily_email_cap = 10`, `send_mode = "dry_run"`, `provider = "resend"`.
- `.env` (gitignored): `PLACES_API_KEY`, `RESEND_API_KEY`, optional SMTP creds.
- `.gitignore`: `.env`, `outbox/`, `*.sqlite`/db file, `__pycache__/`.
- **Commands:**
  - `python -m outreach run` — build today's batch (discover → … → draft → save).
  - `python -m outreach serve` — open the dashboard at `localhost:5000`.
  - `python -m outreach send` — process approved email leads (respects dry-run/live + caps).
- Optional Windows Task Scheduler entry runs the morning `run` (Tanner still reviews).

## 12. Error handling

- Places quota/network errors → retry with backoff, log, continue on a partial batch. The daily
  run never hard-crashes.
- Site fetch failure/timeout → recorded as a strong "unreachable" signal, not a crash.
- Send failure → lead marked `send_failed`, kept in queue, surfaced in dashboard; **never**
  marked contacted unless the send is confirmed.
- Re-running `run` the same day is **idempotent** — no duplicate businesses, no re-contacts.

## 13. Testing (TDD — tests first)

- **Unit:** `audit.py` against saved HTML fixtures (modern / outdated / social-only /
  broken-links) asserting correct findings; `score.py` weight math + capping; `draft.py`
  channel selection + template fill; `store.py` never-repeat dedup + suppression.
- **Integration:** full `pipeline` on a mocked Places response + fixture sites → 10 ranked
  drafts saved to a temp DB, zero real network.
- **Sending:** dry-run writes `.eml` and sends nothing; compliance footer present; daily cap
  enforced; suppression honored; no double-send.

## 14. Limitations & honest constraints

- **Bad-mobile** and **old-photos** detection are heuristic/best-effort over static HTML; they
  inform but are flagged for Tanner's eyeball, not trusted to auto-send on alone.
- **Google Places API costs per search** — acceptable, but town×category sweeps should be
  scoped and cached to control spend.
- **No automated DM** — IG/FB ToS; manual copy-paste only.
- **Cold-email deliverability** depends on correct SPF/DKIM and low volume; the ≤10/day cap and
  domain sending are deliberate.

## 15. Future (Phase 2+)

- **Headless mobile check** via Playwright (already set up in the promo-reel pipeline) — real
  rendered mobile screenshots + accurate bad-mobile detection, shown in the dashboard.
- **Follow-up sequences** (a second touch after N days for no-reply leads), within compliance.
- **Unattended morning send** toggle once Tanner trusts the drafts.
- Optional reply tracking / simple CRM stage beyond `status`.

# Social Lookup — Design Spec

- **Date:** 2026-06-20
- **Owner:** Tanner / Frontline Web Designs
- **Status:** Approved design, pre-implementation
- **Repo:** `C:\Users\Tanne\frontline-outreach` (master)
- **Builds on:** the Frontline Outreach tool (already shipped and merged)

## 1. Goal

For **social-only / no-website** leads (e.g. *Da Green Coffee Bar* — 301 reviews, no
website), automatically find the business's **Instagram/Facebook** handle and surface it in
the dashboard next to the already-drafted DM, with a one-click **"Open profile."** Tanner
reviews and sends the DM manually. This turns leads that currently route to `phone`/`none`
into actionable `dm` leads.

**Non-goal / hard constraint:** the tool does NOT send Instagram/Facebook DMs. Meta has no
API for cold DMs and automated DM-sending violates their ToS (account-ban risk). Sending stays
manual; the human (Tanner) is also the final check against wrong-account DMs.

## 2. Why this is small

The existing tool already has most of the wiring:
- `Business` has `instagram` and `facebook` fields.
- `draft.choose_channel` already routes to `dm` when `instagram` or `facebook` is set
  (priority: email → dm → phone → none).
- The dashboard already renders an **"Open profile"** link for `dm` leads.

The only missing piece is **populating** those fields for businesses with no website (today
they're only filled by scraping a website, which these leads don't have). This feature adds
that lookup plus a confidence flag.

## 3. Data source (decided)

**Google Custom Search JSON API** (Programmable Search Engine). Official, reliable, no
scraping/blocking. Free for 100 queries/day (covers ~10 leads/day with wide margin), then
~$5/1000. One-time setup: enable Custom Search API + create a Programmable Search Engine to get
a CX id (same Google Cloud ecosystem as the Places key).

## 4. New module: `outreach/socials.py`

Single responsibility: business → best social handle + confidence. HTTP is injectable for
testing.

```python
CSE_URL = "https://www.googleapis.com/customsearch/v1"
STOPWORDS = {"the", "a", "an", "of", "and", "&", "llc", "inc", "co", "hi", "maui", "hawaii"}

def name_match_confidence(business_name, result_text) -> str:
    # token-overlap of name tokens (minus STOPWORDS) found in result_text (title + slug),
    # case-insensitive, punctuation-stripped. ratio >= threshold -> "high" else "low".

def find_social(business, api_key, cx, get=requests.get,
                query_suffix="instagram", threshold=0.6) -> tuple:
    # returns (url, platform, confidence): platform in {"instagram","facebook"},
    # confidence in {"high","low"}; or (None, None, "none") if nothing found / on error.
```

Behavior:
- Query text: `f"{business.name} {business.town} Maui {query_suffix}"`.
- GET `CSE_URL` with params `key`, `cx`, `q`, `num=5`. Parse `items`.
- **IG-first:** first `item.link` whose host contains `instagram.com`; else first whose host
  contains `facebook.com`/`fb.com`.
- Confidence from `name_match_confidence(business.name, matched_item.title + " " + handle_slug)`
  against `threshold`.
- Any exception, missing key/cx, empty `items`, or no social link → return `(None, None, "none")`.

## 5. Data model

- `Business`: add `social_confidence: str = ""` (`"high" | "low" | ""`).
- `store` `businesses` table: add column `social_confidence TEXT DEFAULT ''`.
  - `upsert_business` writes it (in the ON CONFLICT update set too).
  - `todays_batch` SELECT includes `b.social_confidence`.
- No other schema changes. (Existing DBs: a one-line `ALTER TABLE ... ADD COLUMN` guard in
  `init_db`, or document that the dev deletes `outreach.sqlite`. See §9.)

## 6. Pipeline change (`pipeline.run_daily`)

Reorder so social lookups run only for the final batch (≤ `batch_size` Custom Search calls per
run):

1. discover → dedupe by place_id → `store.filter_unseen`
2. for each fresh: `audit_one` → `score.score_findings`; keep those with score > 0 (as
   `(business, findings, score, summary)` tuples — **no draft yet**)
3. sort by score desc, take top `batch_size`
4. for each of the top:
   - if it has no real website and no `instagram`/`facebook` yet AND socials enabled →
     `socials.find_social(...)`; set `business.instagram` or `business.facebook` and
     `business.social_confidence`
   - then `draft.build_draft(...)` → `Lead`
5. `store.save_lead` each

A new module-level wrapper `social_lookup_one(business, config)` (like `audit_one`) so tests can
monkeypatch it.

## 7. Config & secrets

- `.env`: `GOOGLE_CSE_KEY`, `GOOGLE_CSE_CX`.
- `config.toml` new block:
  ```toml
  [socials]
  enabled = true
  query_suffix = "instagram"
  confidence_threshold = 0.6
  ```
- **Optional by design:** if `enabled = false`, or `GOOGLE_CSE_KEY`/`GOOGLE_CSE_CX` are unset,
  the lookup is skipped — leads keep their existing `phone`/`none` channel and the run proceeds
  normally. The tool never depends on socials to function.

## 8. Dashboard

`dm` cards already show "Open profile." Add a confidence cue next to it:
- `social_confidence == "low"` → ⚠ text note "verify this is the right account" (icon **and**
  text, not color-only; `aria-label` for screen readers — WCAG AA).
- `"high"` → a subtle ✓ (or nothing).

Template + small CSS only; no structural change. The server already passes the row through, so
`social_confidence` just needs to be read in the template.

## 9. Error handling

- Socials disabled / keys missing → skip lookup silently; lead keeps existing channel.
- CSE HTTP error, quota exhausted, empty/malformed results → `find_social` returns
  `(None, None, "none")`, logged, run continues. The daily run never crashes on social lookup.
- Schema migration: `init_db` runs an idempotent `ALTER TABLE businesses ADD COLUMN
  social_confidence TEXT DEFAULT ''` wrapped to ignore "duplicate column" errors, so existing
  `outreach.sqlite` files upgrade cleanly.

## 10. Testing (TDD; all network mocked via injected `get`)

- `socials.name_match_confidence`: exact name in text → "high"; unrelated text → "low";
  stopwords ignored.
- `socials.find_social` with mocked CSE JSON:
  - IG result whose title matches name → `(ig_url, "instagram", "high")`
  - no IG item but a FB item → facebook fallback
  - IG result with mismatched title → confidence `"low"`
  - empty `items` / HTTP error (get raises) → `(None, None, "none")`
- `store`: `social_confidence` column round-trips via `upsert_business` → `todays_batch`;
  `init_db` is idempotent on a DB that already has the column.
- `pipeline` (monkeypatch `social_lookup_one`): a social-only top lead gains an Instagram handle
  → channel becomes `dm`, `social_confidence` persisted; lookup is NOT called for non-social or
  already-handled leads, and is capped at the top `batch_size`.
- `server`: a low-confidence `dm` lead renders the ⚠ verify marker; a high-confidence one does
  not.

## 11. Out of scope

- Automated DM sending (ToS — permanent).
- Showing multiple candidate handles / a picker (chose best-match + confidence instead).
- On-demand dashboard lookup (chose in-pipeline).
- Enriching socials for leads that already have a website (those already get socials scraped
  from the site).

## 12. Setup notes (for README)

1. Google Cloud → enable **Custom Search API** (can reuse the Places project/key).
2. Create a **Programmable Search Engine** (search the entire web) → copy its **CX** id.
3. Add `GOOGLE_CSE_KEY` and `GOOGLE_CSE_CX` to `.env`.
4. `[socials] enabled = true` in `config.toml`.

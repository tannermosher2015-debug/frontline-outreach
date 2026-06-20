# Social Lookup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** For social-only / no-website leads, find the business's Instagram/Facebook handle (Google Custom Search) and surface it in the dashboard with a confidence flag, turning `phone`/`none` leads into actionable `dm` leads. DM sending stays manual.

**Architecture:** A new pure-ish `socials.py` module (HTTP injectable) does the lookup + confidence scoring. `pipeline.run_daily` is reordered so lookups run only for the final top-`batch_size` social-only leads (≤ batch_size Custom Search calls/run). One new `Business` field + one `businesses` column carry the confidence. The existing `choose_channel`/draft/dashboard logic already handles `dm` leads, so the surface area is small. Feature is optional: with `[socials] enabled=false` or missing keys, lookups are skipped and the run is unchanged.

**Tech Stack:** Python 3.12, `requests`, Flask/Jinja, SQLite, Google Custom Search JSON API. Tests: pytest, all network mocked via an injected `get`. Windows + PowerShell; run tests via `.\.venv\Scripts\python.exe -m pytest`.

---

## File Structure

```
outreach/
  socials.py        # NEW: name_match_confidence(), find_social()
  models.py         # MODIFY: Business.social_confidence field
  store.py          # MODIFY: column + idempotent migration + upsert + todays_batch
  pipeline.py       # MODIFY: social_lookup_one() + run_daily reorder
  web/templates/dashboard.html  # MODIFY: confidence marker on dm cards
  web/static/app.css            # MODIFY: marker styles
config.toml         # MODIFY: [socials] block
.env.example        # MODIFY: GOOGLE_CSE_KEY / GOOGLE_CSE_CX
README.md           # MODIFY: social-lookup setup notes
tests/
  test_socials.py   # NEW
  test_store.py     # MODIFY: column round-trip + migration
  test_pipeline.py  # MODIFY: social lookup → dm
  test_server.py    # MODIFY: confidence marker renders
```

Note: `server.py` needs NO change — it already passes each `todays_batch` row dict to the template, so the new `social_confidence` key flows through automatically once `todays_batch` selects it.

---

## Task 1: Add `social_confidence` to the Business model

**Files:**
- Modify: `outreach/models.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Write the failing test (append to `tests/test_models.py`)**

```python
def test_business_has_social_confidence_default():
    b = Business(place_id="p", name="N")
    assert b.social_confidence == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_models.py::test_business_has_social_confidence_default -v`
Expected: FAIL (`AttributeError: 'Business' object has no attribute 'social_confidence'`)

- [ ] **Step 3: Add the field**

In `outreach/models.py`, the `Business` dataclass currently ends with `business_status: str = "OPERATIONAL"`. Add one line after it (a defaulted field at the END keeps positional construction safe):

```python
    business_status: str = "OPERATIONAL"
    social_confidence: str = ""   # "high" | "low" | "" (set by social lookup)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_models.py -v`
Expected: PASS (all model tests)

- [ ] **Step 5: Commit**

```
git add outreach/models.py tests/test_models.py
git commit -m "feat: add Business.social_confidence field"
```

---

## Task 2: `socials.name_match_confidence`

**Files:**
- Create: `outreach/socials.py`
- Test: `tests/test_socials.py`

- [ ] **Step 1: Write the failing test (`tests/test_socials.py`)**

```python
from outreach.socials import name_match_confidence

def test_high_when_name_tokens_present():
    assert name_match_confidence(
        "Da Green Coffee Bar",
        "Da Green Coffee Bar (@dagreencoffeebar) - Instagram") == "high"

def test_low_when_unrelated():
    assert name_match_confidence("Da Green Coffee Bar", "Maui Tacos Kihei HI") == "low"

def test_stopwords_ignored():
    # "The" / "of" / "Maui" are stopwords; "kihei coffee" tokens carry the match
    assert name_match_confidence("The Coffee of Maui", "Kihei Coffee shop") == "high"

def test_empty_name_is_low():
    assert name_match_confidence("", "anything") == "low"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_socials.py -v`
Expected: FAIL (`ModuleNotFoundError: outreach.socials`)

- [ ] **Step 3: Implement (`outreach/socials.py`)**

```python
import re
import requests
from urllib.parse import urlparse

CSE_URL = "https://www.googleapis.com/customsearch/v1"
STOPWORDS = {"the", "a", "an", "of", "and", "&", "llc", "inc", "co",
             "hi", "maui", "hawaii"}

def _tokens(text):
    return [t for t in re.findall(r"[a-z0-9]+", (text or "").lower())
            if t and t not in STOPWORDS]

def name_match_confidence(business_name, result_text, threshold=0.6):
    name_tokens = _tokens(business_name)
    if not name_tokens:
        return "low"
    hay = set(_tokens(result_text))
    hits = sum(1 for t in name_tokens if t in hay)
    ratio = hits / len(name_tokens)
    return "high" if ratio >= threshold else "low"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_socials.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```
git add outreach/socials.py tests/test_socials.py
git commit -m "feat: add name_match_confidence for social lookup"
```

---

## Task 3: `socials.find_social`

**Files:**
- Modify: `outreach/socials.py`
- Modify: `tests/test_socials.py`

- [ ] **Step 1: Write the failing test (append to `tests/test_socials.py`)**

```python
from outreach.socials import find_social
from outreach.models import Business

class FakeResp:
    def __init__(self, payload, raise_exc=None):
        self._payload = payload
        self._raise = raise_exc
    def raise_for_status(self):
        if self._raise:
            raise self._raise
    def json(self):
        return self._payload

def make_get(payload, raise_exc=None):
    def _get(url, params=None, timeout=None):
        return FakeResp(payload, raise_exc)
    return _get

BIZ = Business(place_id="s1", name="Da Green Coffee Bar", town="Kihei")

def test_find_social_instagram_high():
    payload = {"items": [
        {"link": "https://www.instagram.com/dagreencoffeebar/",
         "title": "Da Green Coffee Bar (@dagreencoffeebar) - Instagram"}]}
    url, plat, conf = find_social(BIZ, "k", "cx", get=make_get(payload))
    assert plat == "instagram"
    assert "instagram.com/dagreencoffeebar" in url
    assert conf == "high"

def test_find_social_facebook_fallback():
    payload = {"items": [
        {"link": "https://example.com/listing", "title": "x"},
        {"link": "https://www.facebook.com/dagreencoffee", "title": "Da Green Coffee Bar"}]}
    url, plat, conf = find_social(BIZ, "k", "cx", get=make_get(payload))
    assert plat == "facebook"
    assert "facebook.com/dagreencoffee" in url

def test_find_social_low_confidence_on_mismatch():
    payload = {"items": [
        {"link": "https://www.instagram.com/someoneelse/", "title": "Maui Tacos Kihei"}]}
    url, plat, conf = find_social(BIZ, "k", "cx", get=make_get(payload))
    assert plat == "instagram"
    assert conf == "low"

def test_find_social_empty_items():
    assert find_social(BIZ, "k", "cx", get=make_get({"items": []})) == (None, None, "none")

def test_find_social_http_error():
    g = make_get({}, raise_exc=Exception("boom"))
    assert find_social(BIZ, "k", "cx", get=g) == (None, None, "none")

def test_find_social_missing_keys():
    assert find_social(BIZ, "", "cx", get=make_get({"items": []})) == (None, None, "none")
    assert find_social(BIZ, "k", "", get=make_get({"items": []})) == (None, None, "none")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_socials.py -v`
Expected: FAIL (`ImportError: cannot import name 'find_social'`)

- [ ] **Step 3: Implement (append to `outreach/socials.py`)**

```python
def _platform(url):
    host = urlparse(url or "").netloc.lower()
    if "instagram.com" in host:
        return "instagram"
    if "facebook.com" in host or "fb.com" in host:
        return "facebook"
    return None

def find_social(business, api_key, cx, get=requests.get,
                query_suffix="instagram", threshold=0.6):
    if not api_key or not cx:
        return (None, None, "none")
    q = f"{business.name} {business.town} Maui {query_suffix}".strip()
    try:
        r = get(CSE_URL, params={"key": api_key, "cx": cx, "q": q, "num": 5},
                timeout=15)
        r.raise_for_status()
        items = r.json().get("items", []) or []
    except Exception:
        return (None, None, "none")

    ig = fb = None
    for it in items:
        plat = _platform(it.get("link", ""))
        if plat == "instagram" and ig is None:
            ig = it
        elif plat == "facebook" and fb is None:
            fb = it
    chosen = ig or fb
    if not chosen:
        return (None, None, "none")

    url = chosen.get("link", "")
    platform = _platform(url)
    slug = urlparse(url).path.strip("/")
    conf = name_match_confidence(
        business.name, (chosen.get("title", "") + " " + slug), threshold)
    return (url, platform, conf)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_socials.py -v`
Expected: PASS (10 passed)

- [ ] **Step 5: Commit**

```
git add outreach/socials.py tests/test_socials.py
git commit -m "feat: add find_social (Custom Search IG/FB lookup, IG-first, graceful)"
```

---

## Task 4: Store — column, idempotent migration, upsert, todays_batch

**Files:**
- Modify: `outreach/store.py`
- Modify: `tests/test_store.py`

- [ ] **Step 1: Write the failing tests (append to `tests/test_store.py`)**

```python
def test_social_confidence_roundtrips():
    conn = fresh_conn()
    lead = make_lead()
    lead.business.instagram = "https://instagram.com/x"
    lead.business.social_confidence = "high"
    store.save_lead(conn, lead, run_date="2026-06-20")
    row = store.todays_batch(conn, "2026-06-20")[0]
    assert row["social_confidence"] == "high"

def test_init_db_is_idempotent():
    conn = store.connect(":memory:")
    store.init_db(conn)
    store.init_db(conn)  # second call must not raise

def test_init_db_migrates_legacy_table():
    conn = store.connect(":memory:")
    # legacy businesses table WITHOUT social_confidence
    conn.executescript(
        "CREATE TABLE businesses (place_id TEXT PRIMARY KEY, name TEXT, category TEXT,"
        " town TEXT, address TEXT, phone TEXT, website TEXT, email TEXT, instagram TEXT,"
        " facebook TEXT, rating REAL, review_count INTEGER, status TEXT, first_seen TEXT);")
    conn.commit()
    store.init_db(conn)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(businesses)").fetchall()]
    assert "social_confidence" in cols
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_store.py -k "social_confidence or idempotent or legacy" -v`
Expected: FAIL (no `social_confidence` column / KeyError)

- [ ] **Step 3a: Add the column to `SCHEMA`**

In `outreach/store.py`, the `businesses` table in `SCHEMA` ends with `status TEXT DEFAULT 'new', first_seen TEXT`. Change that line to add the column:

```sql
CREATE TABLE IF NOT EXISTS businesses (
  place_id TEXT PRIMARY KEY, name TEXT, category TEXT, town TEXT,
  address TEXT, phone TEXT, website TEXT, email TEXT,
  instagram TEXT, facebook TEXT, rating REAL, review_count INTEGER,
  status TEXT DEFAULT 'new', first_seen TEXT, social_confidence TEXT DEFAULT ''
);
```

- [ ] **Step 3b: Make `init_db` migrate legacy DBs idempotently**

Replace the current `init_db`:

```python
def init_db(conn):
    conn.executescript(SCHEMA)
    try:
        conn.execute("ALTER TABLE businesses ADD COLUMN social_confidence TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass  # column already exists — fresh DBs and re-runs both land here
    conn.commit()
```

- [ ] **Step 3c: Persist + read the column**

In `upsert_business`, add `social_confidence` to the insert columns, the values, and the conflict-update set. Replace the `conn.execute(...)` body with:

```python
    conn.execute(
        """INSERT INTO businesses
           (place_id,name,category,town,address,phone,website,email,
            instagram,facebook,rating,review_count,social_confidence,status,first_seen)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,'new',?)
           ON CONFLICT(place_id) DO UPDATE SET
             name=excluded.name, phone=excluded.phone, website=excluded.website,
             email=excluded.email, instagram=excluded.instagram,
             facebook=excluded.facebook, rating=excluded.rating,
             review_count=excluded.review_count,
             social_confidence=excluded.social_confidence""",
        (b.place_id, b.name, b.category, b.town, b.address, b.phone, b.website,
         b.email, b.instagram, b.facebook, b.rating, b.review_count,
         b.social_confidence, _now()),
    )
```

In `todays_batch`, add `b.social_confidence` to the SELECT column list (after `b.status`):

```sql
        SELECT b.place_id, b.name, b.category, b.town, b.phone, b.website,
               b.email, b.instagram, b.facebook, b.status, b.social_confidence,
               a.score, a.summary, a.findings,
               o.channel, o.subject, o.draft_text, o.contacted_at, o.send_status
```

- [ ] **Step 4: Run the full store suite**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_store.py -v`
Expected: PASS (all, including the 3 new tests)

- [ ] **Step 5: Commit**

```
git add outreach/store.py tests/test_store.py
git commit -m "feat: persist social_confidence + idempotent column migration"
```

---

## Task 5: Pipeline — `social_lookup_one` + reorder `run_daily`

**Files:**
- Modify: `outreach/pipeline.py`
- Modify: `tests/test_pipeline.py`

- [ ] **Step 1: Write the failing test (append to `tests/test_pipeline.py`)**

```python
def test_run_daily_social_lookup_makes_dm(monkeypatch):
    conn = store.connect(":memory:"); store.init_db(conn)
    cand = [Business(place_id="s1", name="Da Green Coffee Bar", website="", review_count=300)]
    monkeypatch.setattr(pipeline, "discover_all", lambda cfg, key: cand)
    monkeypatch.setattr(pipeline, "audit_one",
                        lambda b, config, current_year=None: Findings(no_website=True, social_only=True))
    def fake_lookup(b, config):
        b.instagram = "https://instagram.com/dagreencoffeebar"
        b.social_confidence = "high"
    monkeypatch.setattr(pipeline, "social_lookup_one", fake_lookup)
    cfg = dict(CFG, socials={"enabled": True})
    leads = pipeline.run_daily(conn, cfg, api_key="k", run_date="2026-06-20")
    assert len(leads) == 1
    assert leads[0].channel == "dm"
    assert leads[0].business.social_confidence == "high"
    assert store.todays_batch(conn, "2026-06-20")[0]["social_confidence"] == "high"

def test_run_daily_no_lookup_for_site_lead(monkeypatch):
    conn = store.connect(":memory:"); store.init_db(conn)
    cand = [Business(place_id="w1", name="Modern Co", website="https://modern.co", review_count=2)]
    monkeypatch.setattr(pipeline, "discover_all", lambda cfg, key: cand)
    monkeypatch.setattr(pipeline, "audit_one",
                        lambda b, config, current_year=None: Findings(weak_google=True))
    calls = []
    monkeypatch.setattr(pipeline, "social_lookup_one", lambda b, config: calls.append(b.place_id))
    cfg = dict(CFG, socials={"enabled": True})
    pipeline.run_daily(conn, cfg, api_key="k", run_date="2026-06-20")
    assert calls == []  # has a real website -> no social lookup
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_pipeline.py -k "social_lookup or site_lead" -v`
Expected: FAIL (`AttributeError: module 'outreach.pipeline' has no attribute 'social_lookup_one'`)

- [ ] **Step 3a: Import socials**

In `outreach/pipeline.py`, change the import line:

```python
from . import store, discover, audit, score, draft, socials
```

- [ ] **Step 3b: Add `social_lookup_one` (after `audit_one`)**

```python
def social_lookup_one(business, config):
    scfg = config.get("socials", {})
    if not scfg.get("enabled"):
        return
    from .config import get_env
    api_key = get_env("GOOGLE_CSE_KEY")
    cx = get_env("GOOGLE_CSE_CX")
    url, platform, conf = socials.find_social(
        business, api_key, cx,
        query_suffix=scfg.get("query_suffix", "instagram"),
        threshold=scfg.get("confidence_threshold", 0.6))
    if url:
        if platform == "instagram":
            business.instagram = url
        else:
            business.facebook = url
        business.social_confidence = conf
```

- [ ] **Step 3c: Reorder `run_daily`**

Replace the body of `run_daily` (from after `fresh = store.filter_unseen(conn, unique)` to the end) with score-first, then lookup+draft for the top batch only:

```python
def run_daily(conn, config, api_key, run_date=None):
    run_date = run_date or date.today().isoformat()
    weights = config["weights"]

    candidates = discover_all(config, api_key)
    seen_ids, unique = set(), []
    for b in candidates:
        if b.place_id and b.place_id not in seen_ids:
            seen_ids.add(b.place_id); unique.append(b)
    fresh = store.filter_unseen(conn, unique)

    scored = []
    for b in fresh:
        findings = audit_one(b, config)
        sc, summary = score.score_findings(findings, weights)
        if sc <= 0:
            continue
        scored.append((b, findings, sc, summary))

    scored.sort(key=lambda t: t[2], reverse=True)
    top = scored[: config["batch_size"]]

    leads = []
    for b, findings, sc, summary in top:
        has_real_site = bool(b.website) and not audit.is_social_url(b.website)
        if not has_real_site and not (b.instagram or b.facebook):
            social_lookup_one(b, config)
        channel, subject, body = draft.build_draft(b, findings, weights)
        lead = Lead(business=b, findings=findings, score=sc, summary=summary,
                    channel=channel, subject=subject, draft=body)
        leads.append(lead)
        store.save_lead(conn, lead, run_date)
    return leads
```

- [ ] **Step 4: Run the full pipeline suite (existing tests must still pass)**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_pipeline.py -v`
Expected: PASS — the two existing tests (`test_run_daily_builds_ranked_batch`, `test_run_daily_skips_already_seen`) still pass because their `CFG` has no `socials` block, so `social_lookup_one` returns immediately; plus the 2 new tests pass.

- [ ] **Step 5: Commit**

```
git add outreach/pipeline.py tests/test_pipeline.py
git commit -m "feat: social lookup for top social-only leads in pipeline"
```

---

## Task 6: Config + .env example

**Files:**
- Modify: `config.toml`
- Modify: `.env.example`

- [ ] **Step 1: Add the `[socials]` block to `config.toml`**

Append at the end of `config.toml`:

```toml
[socials]
enabled = true
query_suffix = "instagram"
confidence_threshold = 0.6
```

- [ ] **Step 2: Add CSE keys to `.env.example`**

Add these lines under the existing keys in `.env.example`:

```bash
# Social lookup (Google Programmable Search / Custom Search JSON API)
GOOGLE_CSE_KEY=your-google-custom-search-key
GOOGLE_CSE_CX=your-programmable-search-engine-id
```

- [ ] **Step 3: Verify config still loads**

Run: `.\.venv\Scripts\python.exe -c "from outreach import config; c=config.load_config('config.toml'); print(c['socials'])"`
Expected: prints `{'enabled': True, 'query_suffix': 'instagram', 'confidence_threshold': 0.6}`

- [ ] **Step 4: Commit**

```
git add config.toml .env.example
git commit -m "chore: add [socials] config + CSE env keys"
```

---

## Task 7: Dashboard confidence marker

**Files:**
- Modify: `outreach/web/templates/dashboard.html`
- Modify: `outreach/web/static/app.css`
- Modify: `tests/test_server.py`

- [ ] **Step 1: Write the failing test (append to `tests/test_server.py`)**

```python
def test_dm_lead_low_confidence_shows_verify(tmp_path):
    conn = store.connect(":memory:"); store.init_db(conn)
    b = Business(place_id="s1", name="Da Green", town="Kihei",
                 instagram="https://instagram.com/dagreen", social_confidence="low")
    store.save_lead(conn, Lead(business=b, findings=Findings(no_website=True, social_only=True),
                               score=55, summary="no website", channel="dm",
                               subject="", draft="Aloha"), "2026-06-19")
    cfg = dict(CFG, outbox_dir=str(tmp_path / "o"))
    app = server.create_app(cfg, conn=conn, today="2026-06-19", api_key="k")
    app.config.update(TESTING=True)
    resp = app.test_client().get("/")
    assert resp.status_code == 200
    assert b"verify" in resp.data.lower()
    assert b"Open profile" in resp.data

def test_dm_lead_high_confidence_no_verify(tmp_path):
    conn = store.connect(":memory:"); store.init_db(conn)
    b = Business(place_id="s2", name="Kraken", town="Kihei",
                 instagram="https://instagram.com/kraken", social_confidence="high")
    store.save_lead(conn, Lead(business=b, findings=Findings(no_website=True, social_only=True),
                               score=55, summary="no website", channel="dm",
                               subject="", draft="Aloha"), "2026-06-19")
    cfg = dict(CFG, outbox_dir=str(tmp_path / "o"))
    app = server.create_app(cfg, conn=conn, today="2026-06-19", api_key="k")
    app.config.update(TESTING=True)
    resp = app.test_client().get("/")
    assert b"verify" not in resp.data.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_server.py -k "confidence" -v`
Expected: FAIL (no "verify" text in output)

- [ ] **Step 3a: Add the marker to `dashboard.html`**

In `outreach/web/templates/dashboard.html`, find the contact line's dm branch:

```html
        {% elif l.channel == 'dm' %}<a href="{{ l.instagram or l.facebook }}" target="_blank" rel="noopener">Open profile</a>
```

Replace it with (adds the confidence cue; text + icon, with aria-label — not color-only):

```html
        {% elif l.channel == 'dm' %}<a href="{{ l.instagram or l.facebook }}" target="_blank" rel="noopener">Open profile</a>
          {% if l.social_confidence == 'low' %}<span class="verify" role="note" aria-label="Verify this is the right account">&#9888; verify account</span>{% elif l.social_confidence == 'high' %}<span class="ok" aria-label="High confidence match">&#10003;</span>{% endif %}
```

- [ ] **Step 3b: Add styles to `app.css`**

Append to `outreach/web/static/app.css`:

```css
.verify { color: var(--warn); font-size:.85rem; margin-left:.4rem; }
.ok { color: var(--accent); font-size:.85rem; margin-left:.4rem; }
```

- [ ] **Step 4: Run the server suite**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_server.py -v`
Expected: PASS (existing + 2 new)

- [ ] **Step 5: Commit**

```
git add outreach/web/templates/dashboard.html outreach/web/static/app.css tests/test_server.py
git commit -m "feat: dashboard confidence marker on dm leads"
```

---

## Task 8: README setup notes + full-suite check

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add a section to `README.md`**

Append:

```markdown
## Social lookup (optional)

For no-website leads, the tool can find the business's Instagram/Facebook handle via
Google's Custom Search JSON API and show it in the dashboard (DMs stay manual).

1. Google Cloud → enable **Custom Search API** (can reuse your Places project/key).
2. Create a **Programmable Search Engine** that searches the entire web → copy its **CX** id.
3. Add to `.env`:
   ```
   GOOGLE_CSE_KEY=your-key
   GOOGLE_CSE_CX=your-cx-id
   ```
4. In `config.toml`, keep `[socials] enabled = true`.

Free for 100 searches/day (the run uses at most one per social lead, capped at your
`batch_size`). Set `enabled = false` to turn it off — the tool runs fine without it.
```

- [ ] **Step 2: Run the FULL suite (no regressions)**

Run: `.\.venv\Scripts\python.exe -m pytest -q`
Expected: PASS (all tests across the project)

- [ ] **Step 3: Commit**

```
git add README.md
git commit -m "docs: social lookup setup notes"
```

---

## Self-Review

**Spec coverage:**
- §3 data source (Custom Search) → Task 3 `find_social` (CSE_URL) ✓
- §4 socials module (find_social + confidence + IG-first + graceful) → Tasks 2–3 ✓
- §5 data model (Business field + column + migration + upsert + todays_batch) → Tasks 1, 4 ✓
- §6 pipeline reorder + `social_lookup_one` wrapper + ≤batch_size + skip non-social/has-handle → Task 5 ✓
- §7 config `[socials]` + `.env` keys + optional/graceful → Tasks 5 (enabled guard), 6 ✓
- §8 dashboard marker (icon+text, aria, AA) → Task 7 ✓
- §9 error handling (graceful none, idempotent migration) → Tasks 3 (try/except), 4 (ALTER guard) ✓
- §10 testing (confidence, find_social cases, store roundtrip+migration, pipeline→dm + skip, server marker) → Tasks 2,3,4,5,7 ✓
- §12 README setup → Task 8 ✓

**Placeholder scan:** none — every step has concrete code/commands.

**Type consistency:** `find_social(business, api_key, cx, get=, query_suffix=, threshold=)` returns `(url, platform, confidence)` — used consistently in `social_lookup_one`. `social_confidence` field/column/SELECT key/template var spelled identically across Tasks 1, 4, 5, 7. `social_lookup_one(business, config)` defined in Task 5 and monkeypatched with the same signature in its tests. `audit.is_social_url` is an existing function (defined in `audit.py`).

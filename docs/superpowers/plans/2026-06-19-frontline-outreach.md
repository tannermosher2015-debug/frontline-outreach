# Frontline Outreach Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A local daily tool that discovers Maui businesses with weak web presence, audits what each is missing, scores by opportunity, drafts an outreach message in Tanner's voice, and lets him review/send from a local dashboard (auto-email via Resend, dry-run by default), never re-contacting a business.

**Architecture:** Python engine of small pure-ish modules (`discover` → `audit` → `score` → `draft`) orchestrated by `pipeline`, persisted by `store` (SQLite ledger = never-repeat), reviewed via a thin Flask `server`, and sent by `send` (dry-run/live). Most logic is pure functions that take data + a `config` dict, so tests pass literals and HTML strings — almost no HTTP mocking.

**Tech Stack:** Python 3.11+ (uses stdlib `tomllib`), `requests`, `beautifulsoup4`+`lxml`, Flask, `python-dotenv`, SQLite (stdlib), Resend REST API / `smtplib`. Tests: `pytest`. Windows + PowerShell.

---

## File Structure

```
frontline-outreach/
  pyproject.toml              # package + deps
  config.toml                 # targets, weights, caps, mode (committed, non-secret)
  .env.example                # PLACES_API_KEY, RESEND_API_KEY (real .env gitignored)
  .gitignore
  outreach/
    __init__.py
    __main__.py               # CLI: run | serve | send
    models.py                 # Business, Findings, Lead dataclasses
    config.py                 # load_config(), get_env()
    store.py                  # all SQLite I/O + dedup + suppression
    discover.py               # Google Places API
    audit.py                  # the 9 weak-presence checks
    score.py                  # findings -> score + summary
    messages.py               # outreach templates (Tanner's voice)
    draft.py                  # channel selection + template fill
    pipeline.py               # run_daily orchestration
    send.py                   # render + dry-run/live email send
    server.py                 # Flask app + routes
    web/
      templates/dashboard.html
      templates/history.html
      static/app.css
      static/app.js
  tests/
    test_config.py test_store.py test_audit.py test_score.py
    test_draft.py test_discover.py test_pipeline.py test_send.py
    test_server.py
  outbox/                     # dry-run .eml output (gitignored)
```

Each module has one responsibility; `store.py` is the only module that touches SQLite.

---

## Task 1: Project scaffold

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `.env.example`, `config.toml`, `outreach/__init__.py`, `tests/__init__.py`

- [ ] **Step 1: Create `.gitignore`**

```gitignore
.venv/
__pycache__/
*.pyc
.env
outbox/
*.sqlite
*.sqlite3
.pytest_cache/
*.egg-info/
```

- [ ] **Step 2: Create `pyproject.toml`**

```toml
[project]
name = "frontline-outreach"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "requests",
  "beautifulsoup4",
  "lxml",
  "flask",
  "python-dotenv",
]

[project.optional-dependencies]
dev = ["pytest"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools]
packages = ["outreach"]
```

- [ ] **Step 3: Create `config.toml`**

```toml
batch_size = 10
weak_google_threshold = 15
daily_email_cap = 10
send_mode = "dry_run"          # dry_run | live
provider = "resend"            # resend | smtp
from_email = "tanner@frontlinewebdesign.tech"
from_name = "Tanner - Frontline Web Designs"
reply_to = "tanner@frontlinewebdesign.tech"
db_path = "outreach.sqlite"
outbox_dir = "outbox"

towns = ["Kahului", "Kihei", "Wailuku", "Lahaina", "Paia", "Makawao"]
categories = ["restaurants", "landscapers", "auto repair", "hair salons", "general contractors", "fitness studios", "coffee shops"]

[weights]
no_website = 30
social_only = 25
outdated_website = 20
bad_mobile = 20
no_contact_button = 15
weak_google = 15
no_service_pages = 10
broken_links = 10
old_photos = 5

[audit]
broken_link_sample = 10
request_timeout = 8
outdated_year_gap = 3
old_photo_year_gap = 4
```

- [ ] **Step 4: Create `.env.example`**

```bash
# Copy to .env (gitignored) and fill in. Never commit .env.
PLACES_API_KEY=your-google-places-api-key
RESEND_API_KEY=your-resend-api-key
# Optional Gmail SMTP fallback (provider = "smtp"):
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=tannermosher2015@gmail.com
SMTP_PASS=your-gmail-app-password
```

- [ ] **Step 5: Create empty package files**

`outreach/__init__.py`:
```python
```
`tests/__init__.py`:
```python
```

- [ ] **Step 6: Create venv and install (PowerShell)**

Run:
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```
Expected: installs the package + pytest with no errors.

- [ ] **Step 7: Commit**

```powershell
git add .gitignore pyproject.toml config.toml .env.example outreach/__init__.py tests/__init__.py
git commit -m "chore: scaffold frontline-outreach project"
```

---

## Task 2: Data models

**Files:**
- Create: `outreach/models.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Write the failing test**

`tests/test_models.py`:
```python
from outreach.models import Business, Findings, Lead

def test_business_defaults():
    b = Business(place_id="abc", name="Joe's Tacos")
    assert b.website == ""
    assert b.review_count == 0
    assert b.business_status == "OPERATIONAL"

def test_findings_fired_signals():
    f = Findings(no_website=True, weak_google=True)
    assert f.fired() == ["no_website", "weak_google"]

def test_lead_holds_parts():
    b = Business(place_id="x", name="Y")
    f = Findings(no_website=True)
    lead = Lead(business=b, findings=f, score=30, summary="No website")
    assert lead.channel == ""
    assert lead.business.name == "Y"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_models.py -v`
Expected: FAIL (`ModuleNotFoundError: outreach.models`).

- [ ] **Step 3: Write minimal implementation**

`outreach/models.py`:
```python
from dataclasses import dataclass, field

SIGNALS = [
    "no_website", "social_only", "weak_google", "no_contact_button",
    "no_service_pages", "outdated_website", "bad_mobile",
    "broken_links", "old_photos",
]

@dataclass
class Business:
    place_id: str
    name: str
    category: str = ""
    town: str = ""
    address: str = ""
    phone: str = ""
    website: str = ""          # "" if none; may be an IG/FB url
    email: str = ""            # scraped if found
    instagram: str = ""        # profile url if found
    facebook: str = ""         # profile url if found
    rating: float = 0.0
    review_count: int = 0
    business_status: str = "OPERATIONAL"

@dataclass
class Findings:
    no_website: bool = False
    social_only: bool = False
    weak_google: bool = False
    no_contact_button: bool = False
    no_service_pages: bool = False
    outdated_website: bool = False
    bad_mobile: bool = False
    broken_links: bool = False
    old_photos: bool = False
    site_unreachable: bool = False
    details: dict = field(default_factory=dict)

    def fired(self):
        return [s for s in SIGNALS if getattr(self, s)]

@dataclass
class Lead:
    business: Business
    findings: Findings
    score: int
    summary: str
    channel: str = ""          # email | dm | phone | none
    subject: str = ""
    draft: str = ""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_models.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```powershell
git add outreach/models.py tests/test_models.py
git commit -m "feat: add Business/Findings/Lead data models"
```

---

## Task 3: Config loader

**Files:**
- Create: `outreach/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

`tests/test_config.py`:
```python
from outreach.config import load_config

def test_load_config_reads_toml(tmp_path):
    p = tmp_path / "c.toml"
    p.write_text('batch_size = 7\n[weights]\nno_website = 99\n', encoding="utf-8")
    cfg = load_config(str(p))
    assert cfg["batch_size"] == 7
    assert cfg["weights"]["no_website"] == 99

def test_load_config_missing_file_raises(tmp_path):
    import pytest
    with pytest.raises(FileNotFoundError):
        load_config(str(tmp_path / "nope.toml"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL (`ModuleNotFoundError: outreach.config`).

- [ ] **Step 3: Write minimal implementation**

`outreach/config.py`:
```python
import os
import tomllib
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()  # load .env into os.environ if present

def load_config(path="config.toml"):
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Config not found: {p}")
    with open(p, "rb") as f:
        return tomllib.load(f)

def get_env(name, default=None):
    return os.environ.get(name, default)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```powershell
git add outreach/config.py tests/test_config.py
git commit -m "feat: add config loader (toml + .env)"
```

---

## Task 4: SQLite store (the never-repeat ledger)

**Files:**
- Create: `outreach/store.py`
- Test: `tests/test_store.py`

- [ ] **Step 1: Write the failing test**

`tests/test_store.py`:
```python
from outreach import store
from outreach.models import Business, Findings, Lead

def fresh_conn():
    conn = store.connect(":memory:")
    store.init_db(conn)
    return conn

def make_lead(pid="p1", name="Joe's Tacos"):
    b = Business(place_id=pid, name=name, town="Kihei", category="restaurants",
                 phone="808-555-1212", email="joe@tacos.com")
    f = Findings(no_website=True, weak_google=True)
    return Lead(business=b, findings=f, score=45, summary="No website",
                channel="email", subject="A quick idea", draft="Aloha...")

def test_upsert_and_seen():
    conn = fresh_conn()
    store.upsert_business(conn, make_lead().business)
    assert store.is_seen(conn, "p1") is True
    assert store.is_seen(conn, "nope") is False

def test_filter_unseen_drops_known():
    conn = fresh_conn()
    store.upsert_business(conn, Business(place_id="p1", name="A"))
    out = store.filter_unseen(conn, [Business(place_id="p1", name="A"),
                                     Business(place_id="p2", name="B")])
    assert [b.place_id for b in out] == ["p2"]

def test_save_and_load_batch():
    conn = fresh_conn()
    store.save_lead(conn, make_lead(), run_date="2026-06-19")
    batch = store.todays_batch(conn, "2026-06-19")
    assert len(batch) == 1
    row = batch[0]
    assert row["name"] == "Joe's Tacos"
    assert row["channel"] == "email"
    assert row["score"] == 45

def test_set_status_and_mark_contacted():
    conn = fresh_conn()
    store.save_lead(conn, make_lead(), run_date="2026-06-19")
    store.mark_contacted(conn, "p1", channel="email")
    row = store.todays_batch(conn, "2026-06-19")[0]
    assert row["status"] == "contacted"
    assert row["contacted_at"] is not None

def test_suppression():
    conn = fresh_conn()
    assert store.is_suppressed(conn, "x@y.com") is False
    store.add_suppression(conn, "x@y.com", reason="opt-out")
    assert store.is_suppressed(conn, "x@y.com") is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_store.py -v`
Expected: FAIL (`ModuleNotFoundError: outreach.store`).

- [ ] **Step 3: Write minimal implementation**

`outreach/store.py`:
```python
import json
import sqlite3
from datetime import datetime, timezone
from .models import Business

SCHEMA = """
CREATE TABLE IF NOT EXISTS businesses (
  place_id TEXT PRIMARY KEY, name TEXT, category TEXT, town TEXT,
  address TEXT, phone TEXT, website TEXT, email TEXT,
  instagram TEXT, facebook TEXT, rating REAL, review_count INTEGER,
  status TEXT DEFAULT 'new', first_seen TEXT
);
CREATE TABLE IF NOT EXISTS audits (
  id INTEGER PRIMARY KEY AUTOINCREMENT, business_id TEXT, run_date TEXT,
  findings TEXT, score INTEGER, summary TEXT
);
CREATE TABLE IF NOT EXISTS outreach (
  id INTEGER PRIMARY KEY AUTOINCREMENT, business_id TEXT, channel TEXT,
  subject TEXT, draft_text TEXT, created_at TEXT, contacted_at TEXT,
  send_status TEXT DEFAULT 'pending'
);
CREATE TABLE IF NOT EXISTS suppression (
  email TEXT PRIMARY KEY, reason TEXT, added_at TEXT
);
"""

def _now():
    return datetime.now(timezone.utc).isoformat()

def connect(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(conn):
    conn.executescript(SCHEMA)
    conn.commit()

def upsert_business(conn, b: Business):
    conn.execute(
        """INSERT INTO businesses
           (place_id,name,category,town,address,phone,website,email,
            instagram,facebook,rating,review_count,status,first_seen)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,'new',?)
           ON CONFLICT(place_id) DO UPDATE SET
             name=excluded.name, phone=excluded.phone, website=excluded.website,
             email=excluded.email, instagram=excluded.instagram,
             facebook=excluded.facebook, rating=excluded.rating,
             review_count=excluded.review_count""",
        (b.place_id, b.name, b.category, b.town, b.address, b.phone, b.website,
         b.email, b.instagram, b.facebook, b.rating, b.review_count, _now()),
    )
    conn.commit()

def is_seen(conn, place_id):
    cur = conn.execute("SELECT 1 FROM businesses WHERE place_id=?", (place_id,))
    return cur.fetchone() is not None

def filter_unseen(conn, businesses):
    return [b for b in businesses if not is_seen(conn, b.place_id)]

def save_lead(conn, lead, run_date):
    upsert_business(conn, lead.business)
    conn.execute(
        "INSERT INTO audits (business_id,run_date,findings,score,summary) VALUES (?,?,?,?,?)",
        (lead.business.place_id, run_date,
         json.dumps(lead.findings.fired()), lead.score, lead.summary),
    )
    conn.execute(
        """INSERT INTO outreach
           (business_id,channel,subject,draft_text,created_at,send_status)
           VALUES (?,?,?,?,?, 'pending')""",
        (lead.business.place_id, lead.channel, lead.subject, lead.draft, _now()),
    )
    conn.commit()

def todays_batch(conn, run_date):
    cur = conn.execute(
        """SELECT b.place_id, b.name, b.category, b.town, b.phone, b.website,
                  b.email, b.instagram, b.facebook, b.status,
                  a.score, a.summary, a.findings,
                  o.channel, o.subject, o.draft_text, o.contacted_at, o.send_status
           FROM audits a
           JOIN businesses b ON b.place_id = a.business_id
           JOIN outreach  o ON o.business_id = a.business_id
           WHERE a.run_date = ?
           ORDER BY a.score DESC""",
        (run_date,),
    )
    return [dict(r) for r in cur.fetchall()]

def set_status(conn, place_id, status):
    conn.execute("UPDATE businesses SET status=? WHERE place_id=?", (status, place_id))
    conn.commit()

def mark_contacted(conn, place_id, channel):
    conn.execute("UPDATE businesses SET status='contacted' WHERE place_id=?", (place_id,))
    conn.execute(
        "UPDATE outreach SET contacted_at=?, send_status='sent', channel=? WHERE business_id=?",
        (_now(), channel, place_id),
    )
    conn.commit()

def set_send_status(conn, place_id, send_status):
    conn.execute("UPDATE outreach SET send_status=? WHERE business_id=?",
                 (send_status, place_id))
    conn.commit()

def update_draft(conn, place_id, draft_text):
    conn.execute("UPDATE outreach SET draft_text=? WHERE business_id=?",
                 (draft_text, place_id))
    conn.commit()

def is_suppressed(conn, email):
    if not email:
        return False
    cur = conn.execute("SELECT 1 FROM suppression WHERE email=?", (email,))
    return cur.fetchone() is not None

def add_suppression(conn, email, reason=""):
    conn.execute(
        "INSERT OR IGNORE INTO suppression (email,reason,added_at) VALUES (?,?,?)",
        (email, reason, _now()),
    )
    conn.commit()

def emails_sent_on(conn, run_date):
    cur = conn.execute(
        "SELECT COUNT(*) AS n FROM outreach WHERE channel='email' "
        "AND send_status='sent' AND substr(contacted_at,1,10)=?",
        (run_date,),
    )
    return cur.fetchone()["n"]

def history(conn):
    cur = conn.execute(
        """SELECT b.name, b.town, b.status, o.channel, o.contacted_at
           FROM businesses b JOIN outreach o ON o.business_id=b.place_id
           WHERE b.status IN ('contacted','replied','client','skipped')
           ORDER BY o.contacted_at DESC"""
    )
    return [dict(r) for r in cur.fetchall()]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_store.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```powershell
git add outreach/store.py tests/test_store.py
git commit -m "feat: add SQLite store with never-repeat ledger + suppression"
```

---

## Task 5: Audit — HTML heuristics (mobile, contact, service pages, outdated)

**Files:**
- Create: `outreach/audit.py`
- Test: `tests/test_audit.py`

- [ ] **Step 1: Write the failing test**

`tests/test_audit.py`:
```python
from outreach.audit import (
    has_viewport, has_contact, has_service_pages, looks_outdated, find_email,
)

MODERN = """<html><head><meta name="viewport" content="width=device-width">
<title>Joe</title></head><body>
<nav><a href="/services">Services</a><a href="/about">About</a>
<a href="/contact">Contact</a></nav>
<a href="mailto:joe@x.com">Email</a><a href="tel:8085551212">Call</a>
<footer>(c) 2026 Joe</footer></body></html>"""

OUTDATED = """<html><head><title>Old</title></head>
<body><center><font size=3>Welcome</font></center>
<p>Best tacos</p><footer>Copyright 2014</footer></body></html>"""

def soup(html):
    from bs4 import BeautifulSoup
    return BeautifulSoup(html, "lxml")

def test_has_viewport():
    assert has_viewport(soup(MODERN)) is True
    assert has_viewport(soup(OUTDATED)) is False

def test_has_contact():
    assert has_contact(soup(MODERN)) is True
    assert has_contact(soup(OUTDATED)) is False

def test_has_service_pages():
    assert has_service_pages(soup(MODERN)) is True
    assert has_service_pages(soup(OUTDATED)) is False

def test_looks_outdated_old_copyright_and_tags():
    fired, details = looks_outdated(OUTDATED, soup(OUTDATED), current_year=2026, gap=3)
    assert fired is True
    assert "old_copyright" in details["reasons"] or "deprecated_tags" in details["reasons"]

def test_looks_outdated_false_for_modern():
    fired, _ = looks_outdated(MODERN, soup(MODERN), current_year=2026, gap=3)
    assert fired is False

def test_find_email():
    assert find_email(soup(MODERN), MODERN) == "joe@x.com"
    assert find_email(soup(OUTDATED), OUTDATED) == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_audit.py -v`
Expected: FAIL (`ModuleNotFoundError: outreach.audit`).

- [ ] **Step 3: Write minimal implementation**

`outreach/audit.py`:
```python
import re

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
SERVICE_WORDS = ("service", "menu", "pricing", "products", "offerings", "shop", "book")

def has_viewport(soup):
    for m in soup.find_all("meta"):
        if (m.get("name") or "").lower() == "viewport":
            return True
    return False

def has_contact(soup):
    for a in soup.find_all("a", href=True):
        href = a["href"].lower()
        if href.startswith("mailto:") or href.startswith("tel:"):
            return True
        if "contact" in href or "contact" in a.get_text(strip=True).lower():
            return True
    if soup.find("form"):
        return True
    return False

def has_service_pages(soup):
    for a in soup.find_all("a", href=True):
        text = (a.get_text(strip=True) + " " + a["href"]).lower()
        if any(w in text for w in SERVICE_WORDS):
            return True
    return False

def looks_outdated(html, soup, current_year, gap):
    reasons = []
    if not has_viewport(soup):
        reasons.append("no_viewport")
    if soup.find("font") or soup.find("center") or soup.find_all("table"):
        if soup.find("font") or soup.find("center"):
            reasons.append("deprecated_tags")
    for m in re.findall(r"(?:copyright|\(c\)|©)\s*(\d{4})", html, re.I):
        if int(m) <= current_year - gap:
            reasons.append("old_copyright")
            break
    if re.search(r"jquery[/-]1\.\d", html, re.I):
        reasons.append("old_jquery")
    return (len(reasons) > 0, {"reasons": reasons})

def find_email(soup, html):
    for a in soup.find_all("a", href=True):
        if a["href"].lower().startswith("mailto:"):
            addr = a["href"][7:].split("?")[0].strip()
            if EMAIL_RE.fullmatch(addr):
                return addr
    m = EMAIL_RE.search(html)
    return m.group(0) if m else ""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_audit.py -v`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```powershell
git add outreach/audit.py tests/test_audit.py
git commit -m "feat: add HTML audit heuristics (mobile/contact/services/outdated/email)"
```

---

## Task 6: Audit — links, photos, socials, and `audit_business` orchestration

**Files:**
- Modify: `outreach/audit.py`
- Modify: `tests/test_audit.py`

- [ ] **Step 1: Write the failing test (append)**

Append to `tests/test_audit.py`:
```python
from outreach.audit import (
    find_socials, check_broken_links, detect_old_photos, audit_business,
)
from outreach.models import Business

LINKS = """<html><body>
<a href="/ok">ok</a><a href="/dead">dead</a>
<a href="https://instagram.com/joestacos">IG</a>
<img src="/img/menu-2018.jpg"><img src="/logo.png"></body></html>"""

def test_find_socials():
    s = soup(LINKS)
    socials = find_socials(s)
    assert "instagram.com/joestacos" in socials["instagram"]

def test_check_broken_links_uses_injected_head():
    def fake_head(url, timeout):
        class R: pass
        r = R(); r.status_code = 404 if url.endswith("/dead") else 200
        return r
    fired, details = check_broken_links(soup(LINKS), "https://x.com", fake_head, cap=10, timeout=5)
    assert fired is True
    assert any("/dead" in u for u in details["broken"])

def test_detect_old_photos_by_year_in_filename():
    fired, _ = detect_old_photos(soup(LINKS), current_year=2026, gap=4)
    assert fired is True   # menu-2018 is >= 4 years old

def test_audit_business_no_website_sets_signals():
    b = Business(place_id="p", name="N", website="", review_count=2)
    f = audit_business(b, config={"weak_google_threshold": 15,
                                  "audit": {"broken_link_sample": 10, "request_timeout": 8,
                                            "outdated_year_gap": 3, "old_photo_year_gap": 4}},
                       fetch=None, current_year=2026)
    assert f.no_website is True
    assert f.social_only is True
    assert f.weak_google is True

def test_audit_business_with_site_uses_fetch():
    b = Business(place_id="p", name="N", website="https://joe.com", review_count=100)
    def fake_fetch(url, timeout):
        return MODERN
    f = audit_business(b, config={"weak_google_threshold": 15,
                                  "audit": {"broken_link_sample": 10, "request_timeout": 8,
                                            "outdated_year_gap": 3, "old_photo_year_gap": 4}},
                       fetch=fake_fetch, head=lambda u, timeout: type("R", (), {"status_code": 200})(),
                       current_year=2026)
    assert f.no_website is False
    assert f.no_contact_button is False
    assert f.weak_google is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_audit.py -v`
Expected: FAIL (`ImportError: cannot import name 'find_socials'`).

- [ ] **Step 3: Write minimal implementation (append to `outreach/audit.py`)**

```python
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from .models import Findings

SOCIAL_HOSTS = ("instagram.com", "facebook.com", "fb.com")

def find_socials(soup):
    out = {"instagram": "", "facebook": ""}
    for a in soup.find_all("a", href=True):
        href = a["href"]
        host = urlparse(href).netloc.lower()
        if "instagram.com" in host and not out["instagram"]:
            out["instagram"] = href
        elif ("facebook.com" in host or "fb.com" in host) and not out["facebook"]:
            out["facebook"] = href
    return out

def is_social_url(url):
    host = urlparse(url).netloc.lower()
    return any(h in host for h in SOCIAL_HOSTS)

def check_broken_links(soup, base_url, head, cap, timeout):
    broken, checked = [], 0
    for a in soup.find_all("a", href=True):
        if checked >= cap:
            break
        href = a["href"]
        if href.startswith(("mailto:", "tel:", "#", "javascript:")):
            continue
        url = urljoin(base_url, href)
        try:
            r = head(url, timeout=timeout)
            checked += 1
            if getattr(r, "status_code", 200) >= 400:
                broken.append(url)
        except Exception:
            checked += 1
            broken.append(url)
    return (len(broken) > 0, {"broken": broken})

def detect_old_photos(soup, current_year, gap):
    cutoff = current_year - gap
    for img in soup.find_all("img", src=True):
        for yr in re.findall(r"(19|20)\d{2}", img["src"]):
            year = int(yr + "")  # yr is the 2-digit prefix group; recompute below
    # robust year scan over full src strings
    for img in soup.find_all("img", src=True):
        for m in re.findall(r"((?:19|20)\d{2})", img["src"]):
            if int(m) <= cutoff:
                return (True, {"old_img": img["src"]})
    return (False, {})

def default_fetch(url, timeout):
    headers = {"User-Agent": "Mozilla/5.0 (FrontlineOutreach audit)"}
    r = requests.get(url, timeout=timeout, headers=headers)
    r.raise_for_status()
    return r.text

def audit_business(b, config, fetch=None, head=None, current_year=None):
    from datetime import date
    if current_year is None:
        current_year = date.today().year
    fetch = fetch or default_fetch
    head = head or (lambda u, timeout: requests.head(u, timeout=timeout, allow_redirects=True))
    acfg = config.get("audit", {})
    f = Findings()

    # Business-level signals (no network needed)
    has_real_site = bool(b.website) and not is_social_url(b.website)
    f.no_website = not bool(b.website)
    f.social_only = (not has_real_site)            # no site, or site is just IG/FB
    f.weak_google = b.review_count < config.get("weak_google_threshold", 15)
    if b.website and is_social_url(b.website):
        f.details["social_site"] = b.website

    if not has_real_site:
        # Nothing to fetch; no-website businesses are strong leads as-is.
        return f

    # Site-level signals
    try:
        html = fetch(b.website, timeout=acfg.get("request_timeout", 8))
    except Exception as e:
        f.site_unreachable = True
        f.details["fetch_error"] = str(e)
        return f

    soup = BeautifulSoup(html, "lxml")
    f.bad_mobile = not has_viewport(soup)
    f.no_contact_button = not has_contact(soup)
    f.no_service_pages = not has_service_pages(soup)
    f.outdated_website, od = looks_outdated(html, soup, current_year,
                                            acfg.get("outdated_year_gap", 3))
    f.details["outdated"] = od["reasons"]
    f.broken_links, bl = check_broken_links(
        soup, b.website, head, acfg.get("broken_link_sample", 10),
        acfg.get("request_timeout", 8))
    f.details["broken"] = bl["broken"]
    f.old_photos, _ = detect_old_photos(soup, current_year,
                                        acfg.get("old_photo_year_gap", 4))
    if not b.email:
        b.email = find_email(soup, html)
    socials = find_socials(soup)
    b.instagram = b.instagram or socials["instagram"]
    b.facebook = b.facebook or socials["facebook"]
    return f
```

> Note: remove the dead first loop in `detect_old_photos` — keep only the robust year-scan loop. (Clean copy:)
```python
def detect_old_photos(soup, current_year, gap):
    cutoff = current_year - gap
    for img in soup.find_all("img", src=True):
        for m in re.findall(r"((?:19|20)\d{2})", img["src"]):
            if int(m) <= cutoff:
                return (True, {"old_img": img["src"]})
    return (False, {})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_audit.py -v`
Expected: PASS (10 passed).

- [ ] **Step 5: Commit**

```powershell
git add outreach/audit.py tests/test_audit.py
git commit -m "feat: add link/photo/social audits + audit_business orchestration"
```

---

## Task 7: Scoring

**Files:**
- Create: `outreach/score.py`
- Test: `tests/test_score.py`

- [ ] **Step 1: Write the failing test**

`tests/test_score.py`:
```python
from outreach.score import score_findings, primary_problem
from outreach.models import Findings

WEIGHTS = {"no_website": 30, "social_only": 25, "outdated_website": 20,
           "bad_mobile": 20, "no_contact_button": 15, "weak_google": 15,
           "no_service_pages": 10, "broken_links": 10, "old_photos": 5}

def test_score_sums_and_caps_at_100():
    f = Findings(no_website=True, social_only=True, weak_google=True,
                 bad_mobile=True, outdated_website=True)  # 30+25+15+20+20 = 110 -> 100
    score, summary = score_findings(f, WEIGHTS)
    assert score == 100
    assert "website" in summary.lower()

def test_score_partial():
    f = Findings(no_contact_button=True, weak_google=True)  # 15+15
    score, _ = score_findings(f, WEIGHTS)
    assert score == 30

def test_primary_problem_is_highest_weighted():
    f = Findings(no_contact_button=True, no_website=True)   # no_website weight 30 wins
    assert primary_problem(f, WEIGHTS) == "no_website"

def test_zero_findings():
    score, summary = score_findings(Findings(), WEIGHTS)
    assert score == 0
    assert summary == "No issues detected"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_score.py -v`
Expected: FAIL (`ModuleNotFoundError: outreach.score`).

- [ ] **Step 3: Write minimal implementation**

`outreach/score.py`:
```python
LABELS = {
    "no_website": "no website",
    "social_only": "social media only",
    "weak_google": "weak Google presence",
    "no_contact_button": "no contact button",
    "no_service_pages": "no service pages",
    "outdated_website": "outdated website",
    "bad_mobile": "not mobile-friendly",
    "broken_links": "broken links",
    "old_photos": "old photos",
}

def score_findings(findings, weights):
    fired = findings.fired()
    raw = sum(weights.get(s, 0) for s in fired)
    score = min(100, raw)
    if not fired:
        return 0, "No issues detected"
    summary = " - ".join(LABELS.get(s, s) for s in fired)
    return score, summary

def primary_problem(findings, weights):
    fired = findings.fired()
    if not fired:
        return ""
    return max(fired, key=lambda s: weights.get(s, 0))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_score.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```powershell
git add outreach/score.py tests/test_score.py
git commit -m "feat: add opportunity scoring + primary problem"
```

---

## Task 8: Messages + draft (channel selection + Tanner's voice)

**Files:**
- Create: `outreach/messages.py`
- Create: `outreach/draft.py`
- Test: `tests/test_draft.py`

- [ ] **Step 1: Write the failing test**

`tests/test_draft.py`:
```python
from outreach.draft import choose_channel, build_draft
from outreach.models import Business, Findings

WEIGHTS = {"no_website": 30, "social_only": 25, "outdated_website": 20,
           "bad_mobile": 20, "no_contact_button": 15, "weak_google": 15,
           "no_service_pages": 10, "broken_links": 10, "old_photos": 5}

def test_choose_channel_prefers_email():
    b = Business(place_id="p", name="N", email="a@b.com", instagram="ig", phone="808")
    assert choose_channel(b) == "email"

def test_choose_channel_dm_then_phone():
    assert choose_channel(Business(place_id="p", name="N", instagram="ig", phone="808")) == "dm"
    assert choose_channel(Business(place_id="p", name="N", phone="808")) == "phone"
    assert choose_channel(Business(place_id="p", name="N")) == "none"

def test_build_draft_no_website_email_has_subject_and_optout():
    b = Business(place_id="p", name="Joe's Tacos", email="joe@x.com")
    f = Findings(no_website=True, weak_google=True)
    channel, subject, body = build_draft(b, f, WEIGHTS)
    assert channel == "email"
    assert subject  # non-empty subject for email
    assert "Joe's Tacos" in body
    assert "Frontline Web Designs" in body
    assert "not interested" in body.lower()   # CAN-SPAM opt-out line

def test_build_draft_dm_has_no_optout_footer():
    b = Business(place_id="p", name="Joe's Tacos", instagram="https://instagram.com/joe")
    f = Findings(social_only=True)
    channel, subject, body = build_draft(b, f, WEIGHTS)
    assert channel == "dm"
    assert subject == ""
    assert "Aloha" in body
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_draft.py -v`
Expected: FAIL (`ModuleNotFoundError: outreach.draft`).

- [ ] **Step 3: Write minimal implementation**

`outreach/messages.py`:
```python
# Canonical outreach copy in Tanner's voice. {name} = business name.
# Keys map to the primary problem; "default" is the fallback.

DM_TEMPLATES = {
    "no_website": (
        "Aloha, my name is Tanner with Frontline Web Designs. I'm a local Maui "
        "firefighter and I build clean websites for small businesses on the side. "
        "I came across {name} and noticed you may not have a dedicated website yet. "
        "I'm currently offering a free website sample upon request, so you can see what "
        "your business could look like online before committing to anything. Would you "
        "like me to put together a sample for you?"
    ),
    "outdated_website": (
        "Aloha, my name is Tanner with Frontline Web Designs. I'm a local Maui "
        "firefighter and I build clean, mobile-friendly websites for small businesses. "
        "I checked out {name}'s current website and I think I could help make it look "
        "more modern, easier to use, and better at getting customers to contact you. "
        "I'm offering a free website sample upon request if you'd like to see what a "
        "cleaner version could look like."
    ),
    "social_only": (
        "Aloha, my name is Tanner with Frontline Web Designs. I'm a local Maui "
        "firefighter helping small businesses build clean, professional websites. "
        "{name}'s Instagram looks solid, but having a website can make it easier for "
        "customers to find your services, prices, photos, contact info, and book with "
        "you. I'm offering a free website sample upon request if you'd like to see what "
        "your business could look like online."
    ),
    "weak_google": (
        "Aloha, my name is Tanner with Frontline Web Designs. I'm a local Maui "
        "firefighter who builds clean websites for small businesses on the side. "
        "I came across {name} and a solid website would help more local customers find "
        "and trust you when they search. I'm offering a free website sample upon request "
        "so you can see what it could look like - no commitment."
    ),
    "no_contact_button": (
        "Aloha, my name is Tanner with Frontline Web Designs. I'm a local Maui "
        "firefighter and I build clean, mobile-friendly websites for small businesses. "
        "I looked at {name}'s site and noticed it's hard for customers to reach you "
        "quickly. I'd love to help make it easier for people to call, message, or book. "
        "I'm offering a free website sample upon request if you'd like to see what a "
        "cleaner version could look like."
    ),
    "default": (
        "Aloha, my name is Tanner with Frontline Web Designs. I'm a local Maui "
        "firefighter and I build clean, mobile-friendly websites for small businesses. "
        "I came across {name} and think a refreshed website could help you reach more "
        "customers. I'm offering a free website sample upon request - no commitment. "
        "Would you like me to put one together for you?"
    ),
}

EMAIL_SUBJECTS = {
    "no_website": "A free website sample for {name}",
    "outdated_website": "A cleaner website for {name} (free sample)",
    "social_only": "A website to go with {name}'s Instagram (free sample)",
    "weak_google": "Helping {name} get found online (free sample)",
    "no_contact_button": "Making it easier for {name}'s customers to reach you",
    "default": "A free website sample for {name}",
}

EMAIL_SIGNATURE = (
    "\n\nMahalo,\nTanner\nFrontline Web Designs\nfrontlinewebdesign.tech\n"
)

# CAN-SPAM opt-out line appended to emails only.
EMAIL_OPTOUT = (
    "\n\n---\nYou're receiving this because you run a local Maui business. "
    "If you'd rather not hear from me, just reply \"not interested\" and I won't "
    "follow up.\nFrontline Web Designs, Maui, HI"
)
```

`outreach/draft.py`:
```python
from .messages import DM_TEMPLATES, EMAIL_SUBJECTS, EMAIL_SIGNATURE, EMAIL_OPTOUT
from .score import primary_problem

def choose_channel(business):
    if business.email:
        return "email"
    if business.instagram or business.facebook:
        return "dm"
    if business.phone:
        return "phone"
    return "none"

def _template_key(findings, weights):
    p = primary_problem(findings, weights)
    return p if p in DM_TEMPLATES else "default"

def build_draft(business, findings, weights):
    channel = choose_channel(business)
    key = _template_key(findings, weights)
    body = DM_TEMPLATES[key].format(name=business.name)

    if channel == "email":
        subject = EMAIL_SUBJECTS.get(key, EMAIL_SUBJECTS["default"]).format(name=business.name)
        body = body + EMAIL_SIGNATURE + EMAIL_OPTOUT
        return channel, subject, body
    if channel == "phone":
        # A spoken script; same copy works read aloud.
        return channel, "", body
    return channel, "", body  # dm
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_draft.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```powershell
git add outreach/messages.py outreach/draft.py tests/test_draft.py
git commit -m "feat: add outreach templates + channel selection + draft builder"
```

---

## Task 9: Discover (Google Places API)

**Files:**
- Create: `outreach/discover.py`
- Test: `tests/test_discover.py`

- [ ] **Step 1: Write the failing test**

`tests/test_discover.py`:
```python
from outreach.discover import parse_places_response

SAMPLE = {
  "places": [
    {"id": "p1", "displayName": {"text": "Joe's Tacos"},
     "formattedAddress": "123 Main, Kihei", "nationalPhoneNumber": "(808) 555-1212",
     "rating": 4.1, "userRatingCount": 8, "businessStatus": "OPERATIONAL"},
    {"id": "p2", "displayName": {"text": "Modern Co"},
     "websiteUri": "https://modern.co", "rating": 4.9, "userRatingCount": 320,
     "businessStatus": "OPERATIONAL"},
    {"id": "p3", "displayName": {"text": "Closed Cafe"},
     "businessStatus": "CLOSED_PERMANENTLY"},
  ]
}

def test_parse_maps_fields_and_drops_closed():
    out = parse_places_response(SAMPLE, town="Kihei", category="restaurants")
    ids = [b.place_id for b in out]
    assert ids == ["p1", "p2"]                 # closed one dropped
    joe = out[0]
    assert joe.name == "Joe's Tacos"
    assert joe.phone == "(808) 555-1212"
    assert joe.website == ""
    assert joe.review_count == 8
    assert joe.town == "Kihei"
    assert joe.category == "restaurants"

def test_parse_empty():
    assert parse_places_response({}, "Kihei", "x") == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_discover.py -v`
Expected: FAIL (`ModuleNotFoundError: outreach.discover`).

- [ ] **Step 3: Write minimal implementation**

`outreach/discover.py`:
```python
import time
import requests
from .models import Business

PLACES_URL = "https://places.googleapis.com/v1/places:searchText"
FIELD_MASK = (
    "places.id,places.displayName,places.formattedAddress,"
    "places.nationalPhoneNumber,places.websiteUri,places.rating,"
    "places.userRatingCount,places.businessStatus,nextPageToken"
)

def parse_places_response(data, town, category):
    out = []
    for p in data.get("places", []):
        if p.get("businessStatus") not in (None, "OPERATIONAL"):
            continue
        out.append(Business(
            place_id=p.get("id", ""),
            name=(p.get("displayName") or {}).get("text", ""),
            category=category,
            town=town,
            address=p.get("formattedAddress", ""),
            phone=p.get("nationalPhoneNumber", ""),
            website=p.get("websiteUri", ""),
            rating=float(p.get("rating", 0.0) or 0.0),
            review_count=int(p.get("userRatingCount", 0) or 0),
            business_status=p.get("businessStatus", "OPERATIONAL"),
        ))
    return out

def search(town, category, api_key, max_pages=2, timeout=10, _post=None):
    post = _post or requests.post
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": FIELD_MASK,
    }
    results, page_token = [], None
    for _ in range(max_pages):
        body = {"textQuery": f"{category} in {town}, Maui HI"}
        if page_token:
            body["pageToken"] = page_token
        r = post(PLACES_URL, headers=headers, json=body, timeout=timeout)
        r.raise_for_status()
        data = r.json()
        results.extend(parse_places_response(data, town, category))
        page_token = data.get("nextPageToken")
        if not page_token:
            break
        time.sleep(2)  # Places requires a short delay before nextPageToken works
    return results
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_discover.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```powershell
git add outreach/discover.py tests/test_discover.py
git commit -m "feat: add Google Places discovery + response parser"
```

---

## Task 10: Pipeline (orchestrate the daily run)

**Files:**
- Create: `outreach/pipeline.py`
- Test: `tests/test_pipeline.py`

- [ ] **Step 1: Write the failing test**

`tests/test_pipeline.py`:
```python
from outreach import pipeline, store
from outreach.models import Business, Findings

CFG = {
    "batch_size": 2, "weak_google_threshold": 15,
    "weights": {"no_website": 30, "social_only": 25, "outdated_website": 20,
                "bad_mobile": 20, "no_contact_button": 15, "weak_google": 15,
                "no_service_pages": 10, "broken_links": 10, "old_photos": 5},
    "towns": ["Kihei"], "categories": ["restaurants"],
    "audit": {"broken_link_sample": 10, "request_timeout": 8,
              "outdated_year_gap": 3, "old_photo_year_gap": 4},
}

def test_run_daily_builds_ranked_batch(monkeypatch):
    conn = store.connect(":memory:"); store.init_db(conn)

    candidates = [
        Business(place_id="p1", name="No Site", website="", review_count=2),
        Business(place_id="p2", name="Modern", website="https://m.co", review_count=200),
        Business(place_id="p3", name="Social", website="https://instagram.com/s", review_count=5),
    ]
    monkeypatch.setattr(pipeline, "discover_all", lambda cfg, key: candidates)

    def fake_audit(b, config, current_year=None):
        if b.place_id == "p1": return Findings(no_website=True, social_only=True, weak_google=True)
        if b.place_id == "p2": return Findings()  # clean -> score 0
        return Findings(social_only=True, weak_google=True)
    monkeypatch.setattr(pipeline, "audit_one", fake_audit)

    leads = pipeline.run_daily(conn, CFG, api_key="k", run_date="2026-06-19")
    assert [l.business.place_id for l in leads] == ["p1", "p3"]  # batch_size 2, ranked, clean dropped
    assert leads[0].score >= leads[1].score
    # persisted + never-repeat
    assert len(store.todays_batch(conn, "2026-06-19")) == 2

def test_run_daily_skips_already_seen(monkeypatch):
    conn = store.connect(":memory:"); store.init_db(conn)
    store.upsert_business(conn, Business(place_id="p1", name="Seen"))
    monkeypatch.setattr(pipeline, "discover_all",
                        lambda cfg, key: [Business(place_id="p1", name="Seen", review_count=1)])
    monkeypatch.setattr(pipeline, "audit_one",
                        lambda b, config, current_year=None: Findings(no_website=True))
    leads = pipeline.run_daily(conn, CFG, api_key="k", run_date="2026-06-20")
    assert leads == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_pipeline.py -v`
Expected: FAIL (`ModuleNotFoundError: outreach.pipeline`).

- [ ] **Step 3: Write minimal implementation**

`outreach/pipeline.py`:
```python
from datetime import date
from . import store, discover, audit, score, draft
from .models import Lead

def discover_all(config, api_key):
    out = []
    for town in config["towns"]:
        for category in config["categories"]:
            out.extend(discover.search(town, category, api_key))
    return out

def audit_one(business, config, current_year=None):
    return audit.audit_business(business, config, current_year=current_year)

def run_daily(conn, config, api_key, run_date=None):
    run_date = run_date or date.today().isoformat()
    weights = config["weights"]

    candidates = discover_all(config, api_key)
    # de-dupe within the run by place_id, then drop already-seen
    seen_ids, unique = set(), []
    for b in candidates:
        if b.place_id and b.place_id not in seen_ids:
            seen_ids.add(b.place_id); unique.append(b)
    fresh = store.filter_unseen(conn, unique)

    leads = []
    for b in fresh:
        findings = audit_one(b, config)
        sc, summary = score.score_findings(findings, weights)
        if sc <= 0:
            continue
        channel, subject, body = draft.build_draft(b, findings, weights)
        leads.append(Lead(business=b, findings=findings, score=sc, summary=summary,
                          channel=channel, subject=subject, draft=body))

    leads.sort(key=lambda l: l.score, reverse=True)
    leads = leads[: config["batch_size"]]
    for l in leads:
        store.save_lead(conn, l, run_date)
    return leads
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_pipeline.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```powershell
git add outreach/pipeline.py tests/test_pipeline.py
git commit -m "feat: add daily pipeline (discover->audit->score->draft->save)"
```

---

## Task 11: Send (dry-run by default, Resend/SMTP live)

**Files:**
- Create: `outreach/send.py`
- Test: `tests/test_send.py`

- [ ] **Step 1: Write the failing test**

`tests/test_send.py`:
```python
from pathlib import Path
from outreach import send, store
from outreach.models import Business, Findings, Lead

CFG = {"send_mode": "dry_run", "provider": "resend", "daily_email_cap": 2,
       "from_email": "t@frontlinewebdesign.tech", "from_name": "Tanner",
       "reply_to": "t@frontlinewebdesign.tech", "outbox_dir": "outbox_test"}

def seed(conn, pid="p1", email="joe@x.com"):
    b = Business(place_id=pid, name="Joe", email=email)
    lead = Lead(business=b, findings=Findings(no_website=True), score=30,
                summary="x", channel="email", subject="Hi Joe", draft="Aloha Joe")
    store.save_lead(conn, lead, "2026-06-19")

def test_dry_run_writes_eml_and_does_not_send(tmp_path):
    conn = store.connect(":memory:"); store.init_db(conn)
    seed(conn)
    cfg = dict(CFG, outbox_dir=str(tmp_path / "outbox"))
    sent = send.send_email_lead(conn, "p1", cfg, api_key="k",
                                _transport=lambda *a, **k: (_ for _ in ()).throw(AssertionError("no live send")))
    assert sent["mode"] == "dry_run"
    files = list((tmp_path / "outbox").glob("*.eml"))
    assert len(files) == 1
    assert "Aloha Joe" in files[0].read_text(encoding="utf-8")
    row = store.todays_batch(conn, "2026-06-19")[0]
    assert row["send_status"] == "dry_run"   # not "sent"

def test_suppressed_email_is_skipped(tmp_path):
    conn = store.connect(":memory:"); store.init_db(conn)
    seed(conn, email="opt@x.com")
    store.add_suppression(conn, "opt@x.com", "prior opt-out")
    cfg = dict(CFG, outbox_dir=str(tmp_path / "o"))
    res = send.send_email_lead(conn, "p1", cfg, api_key="k")
    assert res["mode"] == "skipped_suppressed"

def test_daily_cap_blocks_send(tmp_path):
    conn = store.connect(":memory:"); store.init_db(conn)
    seed(conn, "p1", "a@x.com"); seed(conn, "p2", "b@x.com"); seed(conn, "p3", "c@x.com")
    store.mark_contacted(conn, "p1", "email")
    store.mark_contacted(conn, "p2", "email")  # 2 sent today, cap=2
    cfg = dict(CFG, send_mode="live", outbox_dir=str(tmp_path / "o"))
    res = send.send_email_lead(conn, "p3", cfg, api_key="k")
    assert res["mode"] == "capped"

def test_live_send_calls_transport_and_marks_sent(tmp_path):
    conn = store.connect(":memory:"); store.init_db(conn)
    seed(conn)
    calls = {}
    def transport(cfg, api_key, to, subject, body):
        calls["to"] = to; return True
    cfg = dict(CFG, send_mode="live", outbox_dir=str(tmp_path / "o"))
    res = send.send_email_lead(conn, "p1", cfg, api_key="k", _transport=transport)
    assert res["mode"] == "sent"
    assert calls["to"] == "joe@x.com"
    row = store.todays_batch(conn, "2026-06-19")[0]
    assert row["status"] == "contacted"
    assert row["send_status"] == "sent"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_send.py -v`
Expected: FAIL (`ModuleNotFoundError: outreach.send`).

- [ ] **Step 3: Write minimal implementation**

`outreach/send.py`:
```python
import re
from datetime import date
from pathlib import Path
import requests
from . import store

RESEND_URL = "https://api.resend.com/emails"

def _lead_row(conn, place_id):
    for r in store.todays_batch(conn, date.today().isoformat()):
        if r["place_id"] == place_id:
            return r
    # fall back: search any run_date
    cur = conn.execute(
        """SELECT b.place_id,b.name,b.email,o.subject,o.draft_text
           FROM businesses b JOIN outreach o ON o.business_id=b.place_id
           WHERE b.place_id=?""", (place_id,))
    row = cur.fetchone()
    return dict(row) if row else None

def _safe(name):
    return re.sub(r"[^A-Za-z0-9_-]+", "_", name)[:40] or "lead"

def write_eml(cfg, to, subject, body):
    outdir = Path(cfg.get("outbox_dir", "outbox"))
    outdir.mkdir(parents=True, exist_ok=True)
    path = outdir / f"{_safe(to)}.eml"
    content = (f"From: {cfg['from_name']} <{cfg['from_email']}>\n"
               f"To: {to}\nReply-To: {cfg.get('reply_to', cfg['from_email'])}\n"
               f"Subject: {subject}\n\n{body}\n")
    path.write_text(content, encoding="utf-8")
    return path

def resend_transport(cfg, api_key, to, subject, body):
    r = requests.post(RESEND_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"from": f"{cfg['from_name']} <{cfg['from_email']}>", "to": [to],
              "reply_to": cfg.get("reply_to", cfg["from_email"]),
              "subject": subject, "text": body}, timeout=15)
    r.raise_for_status()
    return True

def send_email_lead(conn, place_id, cfg, api_key, run_date=None, _transport=None):
    run_date = run_date or date.today().isoformat()
    row = _lead_row(conn, place_id)
    if not row or not row.get("email"):
        return {"mode": "no_email"}
    to = row["email"]
    if store.is_suppressed(conn, to):
        return {"mode": "skipped_suppressed"}

    subject = row.get("subject") or ""
    body = row.get("draft_text") or ""

    if cfg.get("send_mode") != "live":
        path = write_eml(cfg, to, subject, body)
        store.set_send_status(conn, place_id, "dry_run")
        return {"mode": "dry_run", "path": str(path)}

    # live: enforce daily cap
    if store.emails_sent_on(conn, run_date) >= cfg.get("daily_email_cap", 10):
        return {"mode": "capped"}

    transport = _transport or (resend_transport if cfg.get("provider") == "resend"
                               else smtp_transport)
    try:
        transport(cfg, api_key, to, subject, body)
    except Exception as e:
        store.set_send_status(conn, place_id, "send_failed")
        return {"mode": "send_failed", "error": str(e)}
    store.mark_contacted(conn, place_id, channel="email")
    return {"mode": "sent", "to": to}

def smtp_transport(cfg, api_key, to, subject, body):
    import os, smtplib
    from email.message import EmailMessage
    msg = EmailMessage()
    msg["From"] = f"{cfg['from_name']} <{cfg['from_email']}>"
    msg["To"] = to
    msg["Reply-To"] = cfg.get("reply_to", cfg["from_email"])
    msg["Subject"] = subject
    msg.set_content(body)
    host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
    port = int(os.environ.get("SMTP_PORT", "587"))
    with smtplib.SMTP(host, port) as s:
        s.starttls()
        s.login(os.environ["SMTP_USER"], os.environ["SMTP_PASS"])
        s.send_message(msg)
    return True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_send.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```powershell
git add outreach/send.py tests/test_send.py
git commit -m "feat: add email send (dry-run default, Resend/SMTP live, caps + suppression)"
```

---

## Task 12: Flask server (routes + actions)

**Files:**
- Create: `outreach/server.py`
- Test: `tests/test_server.py`

- [ ] **Step 1: Write the failing test**

`tests/test_server.py`:
```python
from outreach import server, store
from outreach.models import Business, Findings, Lead

CFG = {"db_path": ":memory:", "send_mode": "dry_run", "provider": "resend",
       "daily_email_cap": 10, "from_email": "t@x.com", "from_name": "T",
       "reply_to": "t@x.com", "outbox_dir": "outbox_test"}

def client_with_lead(tmp_path):
    conn = store.connect(":memory:"); store.init_db(conn)
    b = Business(place_id="p1", name="Joe", email="joe@x.com", town="Kihei")
    store.save_lead(conn, Lead(business=b, findings=Findings(no_website=True),
                               score=30, summary="no website", channel="email",
                               subject="Hi", draft="Aloha Joe"), "2026-06-19")
    cfg = dict(CFG, outbox_dir=str(tmp_path / "o"))
    app = server.create_app(cfg, conn=conn, today="2026-06-19", api_key="k")
    app.config.update(TESTING=True)
    return app.test_client(), conn

def test_dashboard_lists_todays_leads(tmp_path):
    c, _ = client_with_lead(tmp_path)
    resp = c.get("/")
    assert resp.status_code == 200
    assert b"Joe" in resp.data
    assert b"no website" in resp.data

def test_skip_sets_status(tmp_path):
    c, conn = client_with_lead(tmp_path)
    resp = c.post("/action/skip", json={"place_id": "p1"})
    assert resp.status_code == 200
    assert store.todays_batch(conn, "2026-06-19")[0]["status"] == "skipped"

def test_mark_contacted(tmp_path):
    c, conn = client_with_lead(tmp_path)
    c.post("/action/contacted", json={"place_id": "p1", "channel": "dm"})
    assert store.todays_batch(conn, "2026-06-19")[0]["status"] == "contacted"

def test_send_action_dry_run(tmp_path):
    c, conn = client_with_lead(tmp_path)
    resp = c.post("/action/send", json={"place_id": "p1"})
    assert resp.get_json()["mode"] == "dry_run"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_server.py -v`
Expected: FAIL (`ModuleNotFoundError: outreach.server`).

- [ ] **Step 3: Write minimal implementation**

`outreach/server.py`:
```python
import json
from datetime import date
from flask import Flask, render_template, request, jsonify
from . import store, send

def create_app(config, conn=None, today=None, api_key=""):
    app = Flask(__name__, template_folder="web/templates", static_folder="web/static")
    today = today or date.today().isoformat()
    _conn = conn or store.connect(config["db_path"])

    def rows():
        out = []
        for r in store.todays_batch(_conn, today):
            r["problems"] = json.loads(r["findings"] or "[]")
            out.append(r)
        return out

    @app.route("/")
    def dashboard():
        leads = rows()
        sent = sum(1 for r in leads if r["status"] == "contacted")
        return render_template("dashboard.html", leads=leads, today=today,
                               sent=sent, total=len(leads))

    @app.route("/history")
    def history():
        return render_template("history.html", rows=store.history(_conn))

    @app.route("/action/skip", methods=["POST"])
    def skip():
        store.set_status(_conn, request.json["place_id"], "skipped")
        return jsonify(ok=True)

    @app.route("/action/contacted", methods=["POST"])
    def contacted():
        d = request.json
        store.mark_contacted(_conn, d["place_id"], d.get("channel", "manual"))
        return jsonify(ok=True)

    @app.route("/action/edit", methods=["POST"])
    def edit():
        d = request.json
        store.update_draft(_conn, d["place_id"], d["draft_text"])
        return jsonify(ok=True)

    @app.route("/action/send", methods=["POST"])
    def send_action():
        res = send.send_email_lead(_conn, request.json["place_id"], config,
                                   api_key=api_key, run_date=today)
        return jsonify(res)

    return app
```

- [ ] **Step 4: Run test to verify it passes**

Note: this task depends on the templates from Task 13. To keep tests green now, create minimal placeholder templates first, then flesh them out in Task 13.

Create `outreach/web/templates/dashboard.html`:
```html
<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Frontline Outreach</title></head><body>
<main>{% for l in leads %}<section>{{ l.name }} - {{ l.summary }}</section>{% endfor %}</main>
</body></html>
```
Create `outreach/web/templates/history.html`:
```html
<!doctype html><html lang="en"><head><meta charset="utf-8"><title>History</title></head>
<body><main>{% for r in rows %}<div>{{ r.name }}</div>{% endfor %}</main></body></html>
```

Run: `pytest tests/test_server.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```powershell
git add outreach/server.py outreach/web/templates/dashboard.html outreach/web/templates/history.html tests/test_server.py
git commit -m "feat: add Flask server with dashboard + action routes"
```

---

## Task 13: Dashboard UI (accessible cards + actions)

**Files:**
- Modify: `outreach/web/templates/dashboard.html`
- Create: `outreach/web/static/app.css`, `outreach/web/static/app.js`
- Modify: `outreach/web/templates/history.html`

- [ ] **Step 1: Flesh out `dashboard.html`** (WCAG AA: landmarks, skip link, labels, focus styles in CSS)

```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Frontline Outreach - {{ today }}</title>
  <link rel="stylesheet" href="{{ url_for('static', filename='app.css') }}">
</head>
<body>
  <a class="skip" href="#main">Skip to content</a>
  <header>
    <h1>Today's Leads</h1>
    <p>{{ today }} - {{ sent }}/{{ total }} contacted - <a href="/history">History</a></p>
  </header>
  <main id="main">
    {% for l in leads %}
    <article class="card" data-id="{{ l.place_id }}" data-channel="{{ l.channel }}">
      <div class="card-head">
        <h2>{{ l.name }}</h2>
        <span class="score" aria-label="Opportunity score">{{ l.score }}</span>
      </div>
      <p class="meta">{{ l.category }} - {{ l.town }} - <span class="channel">{{ l.channel }}</span></p>
      <ul class="chips">{% for p in l.problems %}<li>{{ p|replace('_',' ') }}</li>{% endfor %}</ul>
      <label class="sr-only" for="draft-{{ l.place_id }}">Outreach draft for {{ l.name }}</label>
      <textarea id="draft-{{ l.place_id }}" class="draft">{{ l.draft_text }}</textarea>
      <p class="contact">
        {% if l.channel == 'email' %}Email: {{ l.email }}
        {% elif l.channel == 'dm' %}<a href="{{ l.instagram or l.facebook }}" target="_blank" rel="noopener">Open profile</a>
        {% elif l.channel == 'phone' %}Call: {{ l.phone }}{% endif %}
      </p>
      <div class="actions">
        <button class="copy">Copy</button>
        {% if l.channel == 'email' %}<button class="send">Approve &amp; Send</button>{% endif %}
        <button class="contacted">Mark contacted</button>
        <button class="skip">Skip</button>
        <span class="status" role="status">{{ l.status }}</span>
      </div>
    </article>
    {% else %}
    <p>No leads yet today. Run <code>python -m outreach run</code>.</p>
    {% endfor %}
  </main>
  <script src="{{ url_for('static', filename='app.js') }}"></script>
</body>
</html>
```

- [ ] **Step 2: Create `app.css`** (focus-visible outlines, contrast-safe)

```css
:root { --ink:#1a1a1a; --bg:#f7f6f3; --line:#dcd8cf; --accent:#0b6; --warn:#a33; }
* { box-sizing: border-box; }
body { margin:0; font:16px/1.5 system-ui, sans-serif; color:var(--ink); background:var(--bg); }
.skip { position:absolute; left:-999px; }
.skip:focus { left:8px; top:8px; background:#fff; padding:8px; z-index:10; }
header { padding:1rem 1.25rem; border-bottom:1px solid var(--line); }
h1 { margin:0; font-size:1.4rem; }
main { display:grid; gap:1rem; padding:1.25rem; max-width:780px; margin:0 auto; }
.card { background:#fff; border:1px solid var(--line); border-radius:12px; padding:1rem; }
.card-head { display:flex; justify-content:space-between; align-items:center; }
.card h2 { margin:0; font-size:1.15rem; }
.score { font-weight:700; background:var(--ink); color:#fff; border-radius:999px; padding:2px 10px; }
.meta { color:#555; margin:.25rem 0 .5rem; }
.chips { list-style:none; display:flex; flex-wrap:wrap; gap:.4rem; padding:0; margin:.25rem 0; }
.chips li { background:#f0ede6; border-radius:6px; padding:2px 8px; font-size:.85rem; }
.draft { width:100%; min-height:120px; padding:.6rem; border:1px solid var(--line); border-radius:8px; font:inherit; }
.actions { display:flex; flex-wrap:wrap; gap:.5rem; align-items:center; margin-top:.6rem; }
button { font:inherit; padding:.5rem .8rem; border:1px solid var(--line); border-radius:8px; background:#fff; cursor:pointer; }
button.send { background:var(--accent); color:#fff; border-color:var(--accent); }
button.skip { color:var(--warn); }
:focus-visible { outline:3px solid #0b6; outline-offset:2px; }
.sr-only { position:absolute; width:1px; height:1px; overflow:hidden; clip:rect(0 0 0 0); }
.status { color:#555; font-size:.9rem; }
@media (prefers-reduced-motion: reduce) { * { transition:none !important; } }
```

- [ ] **Step 3: Create `app.js`** (POST actions, copy, optimistic status)

```javascript
async function post(url, body) {
  const r = await fetch(url, {method:"POST", headers:{"Content-Type":"application/json"},
                             body: JSON.stringify(body)});
  return r.json();
}
function cardId(el){ return el.closest(".card").dataset.id; }
function setStatus(el, text){ el.closest(".card").querySelector(".status").textContent = text; }

document.querySelectorAll(".card").forEach(card => {
  const id = card.dataset.id;
  const draft = card.querySelector(".draft");

  card.querySelector(".copy")?.addEventListener("click", async () => {
    await navigator.clipboard.writeText(draft.value);
    setStatus(card.querySelector(".copy"), "copied");
  });
  draft.addEventListener("change", () => post("/action/edit", {place_id:id, draft_text:draft.value}));
  card.querySelector(".skip")?.addEventListener("click", async (e) => {
    await post("/action/skip", {place_id:id}); setStatus(e.target, "skipped");
  });
  card.querySelector(".contacted")?.addEventListener("click", async (e) => {
    await post("/action/contacted", {place_id:id, channel:card.dataset.channel});
    setStatus(e.target, "contacted");
  });
  card.querySelector(".send")?.addEventListener("click", async (e) => {
    e.target.disabled = true;
    const res = await post("/action/send", {place_id:id});
    setStatus(e.target, res.mode === "sent" ? "sent" : res.mode);
    e.target.disabled = false;
  });
});
```

- [ ] **Step 4: Flesh out `history.html`**

```html
<!doctype html>
<html lang="en">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Outreach History</title>
<link rel="stylesheet" href="{{ url_for('static', filename='app.css') }}"></head>
<body>
  <header><h1>History</h1><p><a href="/">Back to today</a></p></header>
  <main>
    <table>
      <thead><tr><th>Business</th><th>Town</th><th>Status</th><th>Channel</th><th>When</th></tr></thead>
      <tbody>
      {% for r in rows %}
        <tr><td>{{ r.name }}</td><td>{{ r.town }}</td><td>{{ r.status }}</td>
            <td>{{ r.channel }}</td><td>{{ r.contacted_at }}</td></tr>
      {% endfor %}
      </tbody>
    </table>
  </main>
</body>
</html>
```

- [ ] **Step 5: Verify routes still render and commit**

Run: `pytest tests/test_server.py -v`
Expected: PASS (4 passed).

```powershell
git add outreach/web/
git commit -m "feat: accessible dashboard UI (cards, actions, history)"
```

---

## Task 14: CLI entrypoint + README

**Files:**
- Create: `outreach/__main__.py`
- Create: `README.md`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test**

`tests/test_cli.py`:
```python
from outreach.__main__ import build_parser

def test_parser_has_subcommands():
    p = build_parser()
    for cmd in ["run", "serve", "send"]:
        ns = p.parse_args([cmd])
        assert ns.command == cmd

def test_run_accepts_date():
    ns = build_parser().parse_args(["run", "--date", "2026-06-19"])
    assert ns.date == "2026-06-19"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli.py -v`
Expected: FAIL (`ModuleNotFoundError` or `ImportError: build_parser`).

- [ ] **Step 3: Write minimal implementation**

`outreach/__main__.py`:
```python
import argparse
import sys
import webbrowser
from datetime import date
from . import config as cfgmod
from . import store, pipeline

def build_parser():
    p = argparse.ArgumentParser(prog="outreach", description="Frontline Outreach lead tool")
    sub = p.add_subparsers(dest="command", required=True)
    pr = sub.add_parser("run", help="Build today's lead batch")
    pr.add_argument("--date", default=None)
    pr.add_argument("--config", default="config.toml")
    ps = sub.add_parser("serve", help="Open the review dashboard")
    ps.add_argument("--config", default="config.toml")
    ps.add_argument("--port", type=int, default=5000)
    pd = sub.add_parser("send", help="Process approved email leads (respects send_mode)")
    pd.add_argument("--config", default="config.toml")
    pd.add_argument("--date", default=None)
    return p

def cmd_run(ns):
    cfg = cfgmod.load_config(ns.config)
    api_key = cfgmod.get_env("PLACES_API_KEY")
    if not api_key:
        print("PLACES_API_KEY not set (.env). Aborting.", file=sys.stderr); return 1
    conn = store.connect(cfg["db_path"]); store.init_db(conn)
    leads = pipeline.run_daily(conn, cfg, api_key, run_date=ns.date)
    print(f"Built {len(leads)} leads for {ns.date or date.today().isoformat()}.")
    for l in leads:
        print(f"  [{l.score:3}] {l.business.name} - {l.channel} - {l.summary}")
    return 0

def cmd_serve(ns):
    from .server import create_app
    cfg = cfgmod.load_config(ns.config)
    store.init_db(store.connect(cfg["db_path"]))
    app = create_app(cfg, api_key=cfgmod.get_env("RESEND_API_KEY", ""))
    url = f"http://127.0.0.1:{ns.port}/"
    print(f"Dashboard at {url}")
    webbrowser.open(url)
    app.run(port=ns.port)
    return 0

def cmd_send(ns):
    from . import send as sender
    cfg = cfgmod.load_config(ns.config)
    api_key = cfgmod.get_env("RESEND_API_KEY", "")
    conn = store.connect(cfg["db_path"]); store.init_db(conn)
    run_date = ns.date or date.today().isoformat()
    n = 0
    for row in store.todays_batch(conn, run_date):
        if row["channel"] == "email" and row["status"] == "new":
            res = sender.send_email_lead(conn, row["place_id"], cfg, api_key, run_date)
            print(f"  {row['name']}: {res['mode']}")
            n += 1
    print(f"Processed {n} email leads (mode={cfg.get('send_mode')}).")
    return 0

def main(argv=None):
    ns = build_parser().parse_args(argv)
    return {"run": cmd_run, "serve": cmd_serve, "send": cmd_send}[ns.command](ns)

if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli.py -v`
Expected: PASS (2 passed).

- [ ] **Step 5: Create `README.md`**

```markdown
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
```

- [ ] **Step 6: Run the full suite**

Run: `pytest -q`
Expected: all tests pass.

- [ ] **Step 7: Commit**

```powershell
git add outreach/__main__.py README.md tests/test_cli.py
git commit -m "feat: add CLI (run/serve/send) + README"
```

---

## Self-Review

**Spec coverage:**
- Discovery via Places API → Task 9 ✓
- 9 audit checks (8 criteria, links/photos split) → Tasks 5–6 ✓
- Scoring + summary + primary problem → Task 7 ✓
- Channel selection + Tanner's verbatim scripts + email subjects/opt-out → Task 8 ✓
- SQLite never-repeat ledger + suppression + status flow → Task 4 ✓
- Pipeline orchestration + dedup + top-10 + idempotent save → Task 10 ✓
- Send: dry-run default, Resend+domain, SMTP fallback, caps, compliance, no double-send → Task 11 ✓
- Dashboard: today view, editable drafts, per-channel actions, history, accessibility → Tasks 12–13 ✓
- Config/secrets/ops + CLI commands → Tasks 1, 3, 14 ✓
- Error handling: site-unreachable as signal (Task 6), send_failed (Task 11), idempotent run (Task 10) ✓
- Testing strategy → tests in every task ✓

**Out of scope (correctly deferred):** auto-DM (never), unattended cron send, Playwright mobile rendering — all Phase 2 per spec §15.

**Placeholder scan:** Task 12 intentionally creates minimal templates so its tests pass before Task 13 fleshes them out — this is sequenced, not a placeholder. No TBD/TODO left in code.

**Type consistency:** `Business`/`Findings`/`Lead` fields, `store` function names, `findings.fired()`, `score_findings`/`primary_problem`, and `send_email_lead`/`mark_contacted`/`set_send_status` signatures are used consistently across Tasks 4–14.

**Note for executor:** In Task 6, `detect_old_photos` is shown with a dead first loop in the inline draft — use the clean copy provided immediately below it.

import json
import sqlite3
from datetime import datetime
from .models import Business

SCHEMA = """
CREATE TABLE IF NOT EXISTS businesses (
  place_id TEXT PRIMARY KEY, name TEXT, category TEXT, town TEXT,
  address TEXT, phone TEXT, website TEXT, email TEXT,
  instagram TEXT, facebook TEXT, rating REAL, review_count INTEGER,
  status TEXT DEFAULT 'new', first_seen TEXT, social_confidence TEXT DEFAULT ''
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
    # Local time on purpose: this is a Hawaii-based daily tool, so "today's batch"
    # and the daily send cap must align with the operator's local day, not UTC.
    return datetime.now().isoformat()

def connect(db_path):
    # check_same_thread=False: the Flask dev server handles each request on its own
    # worker thread, but this is a single-user local tool, so one shared connection
    # is fine (sqlite3 serializes access). Without this, every dashboard request 500s.
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(conn):
    conn.executescript(SCHEMA)
    try:
        conn.execute("ALTER TABLE businesses ADD COLUMN social_confidence TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass  # column already exists — fresh DBs and re-runs both land here
    for col, decl in (("sample_url", "TEXT DEFAULT ''"), ("sample_sent_at", "TEXT")):
        try:
            conn.execute(f"ALTER TABLE businesses ADD COLUMN {col} {decl}")
        except sqlite3.OperationalError:
            pass  # sample-funnel columns; already present on re-runs
    conn.commit()

def upsert_business(conn, b: Business):
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
                  b.email, b.instagram, b.facebook, b.status, b.social_confidence,
                  b.sample_url,
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

def get_business(conn, place_id):
    cur = conn.execute("SELECT * FROM businesses WHERE place_id=?", (place_id,))
    row = cur.fetchone()
    return dict(row) if row else None

def find_by_email(conn, email):
    if not email:
        return None
    cur = conn.execute(
        "SELECT place_id, name, status FROM businesses WHERE lower(email)=lower(?)",
        (email.strip(),))
    row = cur.fetchone()
    return dict(row) if row else None

def set_sample_url(conn, place_id, url):
    conn.execute("UPDATE businesses SET sample_url=? WHERE place_id=?", (url, place_id))
    conn.commit()

def mark_sample_sent(conn, place_id):
    conn.execute(
        "UPDATE businesses SET status='sample_sent', sample_sent_at=? WHERE place_id=?",
        (_now(), place_id))
    conn.commit()

def leads_awaiting_sample_send(conn):
    cur = conn.execute(
        "SELECT place_id, name, email, sample_url FROM businesses "
        "WHERE status='interested' AND sample_url<>'' "
        "AND (sample_sent_at IS NULL OR sample_sent_at='')")
    return [dict(r) for r in cur.fetchall()]

def leads_awaiting_build(conn):
    cur = conn.execute(
        "SELECT place_id, name, category, town, website, phone, email, "
        "instagram, facebook FROM businesses "
        "WHERE status='interested' AND (sample_url IS NULL OR sample_url='')")
    return [dict(r) for r in cur.fetchall()]

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
           WHERE b.status IN ('contacted','replied','interested','sample_sent',
                              'unsubscribed','client','skipped')
           ORDER BY o.contacted_at DESC"""
    )
    return [dict(r) for r in cur.fetchall()]

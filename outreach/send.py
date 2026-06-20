import re
from datetime import date
from pathlib import Path
import requests
from . import store

RESEND_URL = "https://api.resend.com/emails"

def _lead_row(conn, place_id, run_date):
    for r in store.todays_batch(conn, run_date):
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
    row = _lead_row(conn, place_id, run_date)
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

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

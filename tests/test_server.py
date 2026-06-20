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

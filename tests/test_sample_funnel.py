import outreach.store as store
import outreach.send as send
from outreach.replies import classify


def _conn():
    c = store.connect(":memory:")
    store.init_db(c)
    return c


def _add(c, pid="p1", email="owner@shop.com", name="Shop",
         status="interested", sample_url=""):
    c.execute(
        "INSERT INTO businesses (place_id,name,status,email,sample_url,first_seen) "
        "VALUES (?,?,?,?,?, '2026-01-01')", (pid, name, status, email, sample_url))
    c.commit()


def test_sample_dry_run_writes_eml(tmp_path):
    c = _conn()
    _add(c, sample_url="https://demo.frontlinewebdesign.tech/shop")
    cfg = {"send_mode": "dry_run", "outbox_dir": str(tmp_path),
           "from_name": "Tanner", "from_email": "t@x.com",
           "deposit_link_url": "https://buy.stripe.com/test"}
    res = send.send_sample_email(c, "p1", cfg, api_key="")
    assert res["mode"] == "dry_run"
    body = (tmp_path / "sample_owner_shop_com.eml").read_text(encoding="utf-8")
    assert "https://demo.frontlinewebdesign.tech/shop" in body
    assert "https://buy.stripe.com/test" in body
    assert "113 Lili Lehua" in body  # CAN-SPAM postal address present


def test_sample_needs_url_and_link():
    c = _conn()
    _add(c, sample_url="")
    cfg = {"send_mode": "dry_run", "deposit_link_url": "x"}
    assert send.send_sample_email(c, "p1", cfg, api_key="")["mode"] == "no_sample_url"


def test_sample_live_marks_sent_and_guards_repeat():
    c = _conn()
    _add(c, sample_url="https://demo/x")
    sent = []
    def fake(cfg, key, to, subj, body):
        sent.append(to); return True
    cfg = {"send_mode": "live", "provider": "resend", "from_name": "T",
           "from_email": "t@x.com", "deposit_link_url": "https://buy.stripe.com/x"}
    r1 = send.send_sample_email(c, "p1", cfg, api_key="k", _transport=fake)
    assert r1["mode"] == "sent" and sent == ["owner@shop.com"]
    r2 = send.send_sample_email(c, "p1", cfg, api_key="k", _transport=fake)
    assert r2["mode"] == "already_sent" and len(sent) == 1  # never double-charge a lead


def test_suppressed_lead_not_sent():
    c = _conn()
    _add(c, sample_url="https://demo/x")
    store.add_suppression(c, "owner@shop.com", "test")
    cfg = {"send_mode": "live", "provider": "resend", "from_name": "T",
           "from_email": "t@x.com", "deposit_link_url": "x"}
    res = send.send_sample_email(c, "p1", cfg, api_key="k", _transport=lambda *a: True)
    assert res["mode"] == "skipped_suppressed"


def test_classify_intents():
    assert classify("yes please") == "yes"
    assert classify("Not interested, unsubscribe") == "no"
    assert classify("who is this?") == "unclear"


def test_queue_then_ready_transition():
    c = _conn()
    _add(c, sample_url="")  # interested, no sample built yet
    assert [l["place_id"] for l in store.leads_awaiting_build(c)] == ["p1"]
    assert store.leads_awaiting_sample_send(c) == []
    store.set_sample_url(c, "p1", "https://demo/x")
    assert store.leads_awaiting_build(c) == []  # built, no longer in build queue
    assert [l["place_id"] for l in store.leads_awaiting_sample_send(c)] == ["p1"]

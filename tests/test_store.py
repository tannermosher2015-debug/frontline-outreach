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

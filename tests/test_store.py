import threading

from outreach import store
from outreach.models import Business, Findings, Lead

def test_connection_usable_across_threads(tmp_path):
    # Regression: the Flask dashboard serves each request on a worker thread.
    # store.connect must allow cross-thread use (check_same_thread=False), or every
    # dashboard request 500s with "SQLite objects created in a thread...".
    conn = store.connect(str(tmp_path / "t.sqlite"))
    store.init_db(conn)
    errors = []
    def work():
        try:
            store.upsert_business(conn, Business(place_id="p1", name="X"))
            assert store.is_seen(conn, "p1") is True
        except Exception as e:  # noqa: BLE001
            errors.append(e)
    t = threading.Thread(target=work)
    t.start(); t.join()
    assert errors == []

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

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

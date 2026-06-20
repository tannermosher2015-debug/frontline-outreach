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

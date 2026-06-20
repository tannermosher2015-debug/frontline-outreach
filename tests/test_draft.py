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

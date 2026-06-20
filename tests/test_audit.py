from outreach.audit import (
    has_viewport, has_contact, has_service_pages, looks_outdated, find_email,
)
from outreach.audit import (
    find_socials, check_broken_links, detect_old_photos, audit_business,
)
from outreach.models import Business

MODERN = """<html><head><meta name="viewport" content="width=device-width">
<title>Joe</title></head><body>
<nav><a href="/services">Services</a><a href="/about">About</a>
<a href="/contact">Contact</a></nav>
<a href="mailto:joe@x.com">Email</a><a href="tel:8085551212">Call</a>
<footer>(c) 2026 Joe</footer></body></html>"""

OUTDATED = """<html><head><title>Old</title></head>
<body><center><font size=3>Welcome</font></center>
<p>Best tacos</p><footer>Copyright 2014</footer></body></html>"""

def soup(html):
    from bs4 import BeautifulSoup
    return BeautifulSoup(html, "lxml")

def test_has_viewport():
    assert has_viewport(soup(MODERN)) is True
    assert has_viewport(soup(OUTDATED)) is False

def test_has_contact():
    assert has_contact(soup(MODERN)) is True
    assert has_contact(soup(OUTDATED)) is False

def test_has_service_pages():
    assert has_service_pages(soup(MODERN)) is True
    assert has_service_pages(soup(OUTDATED)) is False

def test_looks_outdated_old_copyright_and_tags():
    fired, details = looks_outdated(OUTDATED, soup(OUTDATED), current_year=2026, gap=3)
    assert fired is True
    assert "old_copyright" in details["reasons"] or "deprecated_tags" in details["reasons"]

def test_looks_outdated_false_for_modern():
    fired, _ = looks_outdated(MODERN, soup(MODERN), current_year=2026, gap=3)
    assert fired is False

def test_find_email():
    assert find_email(soup(MODERN), MODERN) == "joe@x.com"
    assert find_email(soup(OUTDATED), OUTDATED) == ""

LINKS = """<html><body>
<a href="/ok">ok</a><a href="/dead">dead</a>
<a href="https://instagram.com/joestacos">IG</a>
<img src="/img/menu-2018.jpg"><img src="/logo.png"></body></html>"""

def test_find_socials():
    s = soup(LINKS)
    socials = find_socials(s)
    assert "instagram.com/joestacos" in socials["instagram"]

def test_check_broken_links_uses_injected_head():
    def fake_head(url, timeout):
        class R: pass
        r = R(); r.status_code = 404 if url.endswith("/dead") else 200
        return r
    fired, details = check_broken_links(soup(LINKS), "https://x.com", fake_head, cap=10, timeout=5)
    assert fired is True
    assert any("/dead" in u for u in details["broken"])

def test_detect_old_photos_by_year_in_filename():
    fired, _ = detect_old_photos(soup(LINKS), current_year=2026, gap=4)
    assert fired is True   # menu-2018 is >= 4 years old

def test_audit_business_no_website_sets_signals():
    b = Business(place_id="p", name="N", website="", review_count=2)
    f = audit_business(b, config={"weak_google_threshold": 15,
                                  "audit": {"broken_link_sample": 10, "request_timeout": 8,
                                            "outdated_year_gap": 3, "old_photo_year_gap": 4}},
                       fetch=None, current_year=2026)
    assert f.no_website is True
    assert f.social_only is True
    assert f.weak_google is True

def test_audit_business_with_site_uses_fetch():
    b = Business(place_id="p", name="N", website="https://joe.com", review_count=100)
    def fake_fetch(url, timeout):
        return MODERN
    f = audit_business(b, config={"weak_google_threshold": 15,
                                  "audit": {"broken_link_sample": 10, "request_timeout": 8,
                                            "outdated_year_gap": 3, "old_photo_year_gap": 4}},
                       fetch=fake_fetch, head=lambda u, timeout: type("R", (), {"status_code": 200})(),
                       current_year=2026)
    assert f.no_website is False
    assert f.no_contact_button is False
    assert f.weak_google is False

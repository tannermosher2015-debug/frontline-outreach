from bs4 import BeautifulSoup
from outreach.audit import audit_business, find_email, find_contact_url
from outreach.models import Business

CFG = {"weak_google_threshold": 15, "audit": {"request_timeout": 5, "broken_link_sample": 0}}


def test_find_email_prefers_site_domain_and_role():
    html = ('<a href="mailto:theme-author@wixpress.com">x</a>'
            ' Reach the shop at hi@joescafe.com or joe.personal@gmail.com')
    soup = BeautifulSoup(html, "lxml")
    # junk (wixpress) dropped; own-domain + role address wins over the gmail
    assert find_email(soup, html, "joescafe.com") == "hi@joescafe.com"


def test_find_email_none_when_only_junk():
    soup = BeautifulSoup('<img src="logo@2x.png"> nothing here', "lxml")
    assert find_email(soup) == ""


def test_find_contact_url_prefers_contact_same_site():
    soup = BeautifulSoup('<a href="/about">About</a><a href="/contact-us">Contact</a>'
                         '<a href="https://facebook.com/x">fb</a>', "lxml")
    assert find_contact_url(soup, "https://joescafe.com") == "https://joescafe.com/contact-us"


def test_audit_follows_contact_page_for_email():
    home = ('<html><head><meta name="viewport" content="x"></head>'
            '<body><a href="/contact">Contact</a></body></html>')
    contact = '<html><body>Email <a href="mailto:info@joescafe.com">info@joescafe.com</a></body></html>'
    pages = {"https://joescafe.com": home, "https://joescafe.com/contact": contact}
    def fetch(url, timeout): return pages[url]
    def head(url, timeout): return type("R", (), {"status_code": 200})()
    b = Business(place_id="p", name="Joe's Cafe", website="https://joescafe.com")
    audit_business(b, CFG, fetch=fetch, head=head)
    assert b.email == "info@joescafe.com"  # found one click deep


def test_audit_no_email_anywhere_does_not_crash():
    home = '<html><head><meta name="viewport" content="x"></head><body>no email</body></html>'
    def fetch(url, timeout): return home
    def head(url, timeout): return type("R", (), {"status_code": 200})()
    b = Business(place_id="p", name="X", website="https://x.com")
    audit_business(b, CFG, fetch=fetch, head=head)
    assert b.email == ""

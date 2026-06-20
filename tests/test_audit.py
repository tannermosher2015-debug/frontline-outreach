from outreach.audit import (
    has_viewport, has_contact, has_service_pages, looks_outdated, find_email,
)

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

import re
import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from .models import Findings

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
SERVICE_WORDS = ("service", "menu", "pricing", "products", "offerings", "shop", "book")


def has_viewport(soup):
    for m in soup.find_all("meta"):
        if (m.get("name") or "").lower() == "viewport":
            return True
    return False


def has_contact(soup):
    for a in soup.find_all("a", href=True):
        href = a["href"].lower()
        if href.startswith("mailto:") or href.startswith("tel:"):
            return True
        if "contact" in href or "contact" in a.get_text(strip=True).lower():
            return True
    if soup.find("form"):
        return True
    return False


def has_service_pages(soup):
    for a in soup.find_all("a", href=True):
        text = (a.get_text(strip=True) + " " + a["href"]).lower()
        if any(w in text for w in SERVICE_WORDS):
            return True
    return False


def looks_outdated(html, soup, current_year, gap):
    reasons = []
    if not has_viewport(soup):
        reasons.append("no_viewport")
    if soup.find("font") or soup.find("center"):
        reasons.append("deprecated_tags")
    for m in re.findall(r"(?:copyright|\(c\)|©)\s*(\d{4})", html, re.I):
        if int(m) <= current_year - gap:
            reasons.append("old_copyright")
            break
    if re.search(r"jquery[/-]1\.\d", html, re.I):
        reasons.append("old_jquery")
    return (len(reasons) > 0, {"reasons": reasons})


def find_email(soup, html):
    for a in soup.find_all("a", href=True):
        if a["href"].lower().startswith("mailto:"):
            addr = a["href"][7:].split("?")[0].strip()
            if EMAIL_RE.fullmatch(addr):
                return addr
    m = EMAIL_RE.search(html)
    return m.group(0) if m else ""


SOCIAL_HOSTS = ("instagram.com", "facebook.com", "fb.com")


def find_socials(soup):
    out = {"instagram": "", "facebook": ""}
    for a in soup.find_all("a", href=True):
        href = a["href"]
        host = urlparse(href).netloc.lower()
        if "instagram.com" in host and not out["instagram"]:
            out["instagram"] = href
        elif ("facebook.com" in host or "fb.com" in host) and not out["facebook"]:
            out["facebook"] = href
    return out


def is_social_url(url):
    host = urlparse(url).netloc.lower()
    return any(h in host for h in SOCIAL_HOSTS)


def check_broken_links(soup, base_url, head, cap, timeout):
    broken, checked = [], 0
    for a in soup.find_all("a", href=True):
        if checked >= cap:
            break
        href = a["href"]
        if href.startswith(("mailto:", "tel:", "#", "javascript:")):
            continue
        url = urljoin(base_url, href)
        try:
            r = head(url, timeout=timeout)
            checked += 1
            if getattr(r, "status_code", 200) >= 400:
                broken.append(url)
        except Exception:
            checked += 1
            broken.append(url)
    return (len(broken) > 0, {"broken": broken})


def detect_old_photos(soup, current_year, gap):
    cutoff = current_year - gap
    for img in soup.find_all("img", src=True):
        for m in re.findall(r"((?:19|20)\d{2})", img["src"]):
            if int(m) <= cutoff:
                return (True, {"old_img": img["src"]})
    return (False, {})


def default_fetch(url, timeout):
    headers = {"User-Agent": "Mozilla/5.0 (FrontlineOutreach audit)"}
    r = requests.get(url, timeout=timeout, headers=headers)
    r.raise_for_status()
    return r.text


def audit_business(b, config, fetch=None, head=None, current_year=None):
    from datetime import date
    if current_year is None:
        current_year = date.today().year
    fetch = fetch or default_fetch
    head = head or (lambda u, timeout: requests.head(u, timeout=timeout, allow_redirects=True))
    acfg = config.get("audit", {})
    f = Findings()

    has_real_site = bool(b.website) and not is_social_url(b.website)
    f.no_website = not bool(b.website)
    f.social_only = (not has_real_site)
    f.weak_google = b.review_count < config.get("weak_google_threshold", 15)
    if b.website and is_social_url(b.website):
        f.details["social_site"] = b.website

    if not has_real_site:
        return f

    try:
        html = fetch(b.website, timeout=acfg.get("request_timeout", 8))
    except Exception as e:
        f.site_unreachable = True
        f.details["fetch_error"] = str(e)
        return f

    soup = BeautifulSoup(html, "lxml")
    f.bad_mobile = not has_viewport(soup)
    f.no_contact_button = not has_contact(soup)
    f.no_service_pages = not has_service_pages(soup)
    f.outdated_website, od = looks_outdated(html, soup, current_year,
                                            acfg.get("outdated_year_gap", 3))
    f.details["outdated"] = od["reasons"]
    f.broken_links, bl = check_broken_links(
        soup, b.website, head, acfg.get("broken_link_sample", 10),
        acfg.get("request_timeout", 8))
    f.details["broken"] = bl["broken"]
    f.old_photos, _ = detect_old_photos(soup, current_year,
                                        acfg.get("old_photo_year_gap", 4))
    if not b.email:
        b.email = find_email(soup, html)
    socials = find_socials(soup)
    b.instagram = b.instagram or socials["instagram"]
    b.facebook = b.facebook or socials["facebook"]
    return f

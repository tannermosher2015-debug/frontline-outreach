import re

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

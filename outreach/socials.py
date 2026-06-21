import re
import requests
from urllib.parse import urlparse

CSE_URL = "https://www.googleapis.com/customsearch/v1"
STOPWORDS = {"the", "a", "an", "of", "and", "&", "llc", "inc", "co",
             "hi", "maui", "hawaii"}

def _tokens(text):
    return [t for t in re.findall(r"[a-z0-9]+", (text or "").lower())
            if t and t not in STOPWORDS]

def name_match_confidence(business_name, result_text, threshold=0.6):
    name_tokens = _tokens(business_name)
    if not name_tokens:
        return "low"
    hay = set(_tokens(result_text))
    hits = sum(1 for t in name_tokens if t in hay)
    ratio = hits / len(name_tokens)
    return "high" if ratio >= threshold else "low"

def _platform(url):
    host = urlparse(url or "").netloc.lower()
    if "instagram.com" in host:
        return "instagram"
    if "facebook.com" in host or "fb.com" in host:
        return "facebook"
    return None

def find_social(business, api_key, cx, get=requests.get,
                query_suffix="instagram", threshold=0.6):
    if not api_key or not cx:
        return (None, None, "none")
    q = f"{business.name} {business.town} Maui {query_suffix}".strip()
    try:
        r = get(CSE_URL, params={"key": api_key, "cx": cx, "q": q, "num": 5},
                timeout=15)
        r.raise_for_status()
        items = r.json().get("items", []) or []
    except Exception:
        return (None, None, "none")

    ig = fb = None
    for it in items:
        plat = _platform(it.get("link", ""))
        if plat == "instagram" and ig is None:
            ig = it
        elif plat == "facebook" and fb is None:
            fb = it
    chosen = ig or fb
    if not chosen:
        return (None, None, "none")

    url = chosen.get("link", "")
    platform = _platform(url)
    slug = urlparse(url).path.strip("/")
    conf = name_match_confidence(
        business.name, (chosen.get("title", "") + " " + slug), threshold)
    return (url, platform, conf)

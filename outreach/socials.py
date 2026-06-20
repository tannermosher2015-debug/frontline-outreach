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

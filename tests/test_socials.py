from outreach.socials import name_match_confidence

def test_high_when_name_tokens_present():
    assert name_match_confidence(
        "Da Green Coffee Bar",
        "Da Green Coffee Bar (@dagreencoffeebar) - Instagram") == "high"

def test_low_when_unrelated():
    assert name_match_confidence("Da Green Coffee Bar", "Maui Tacos Kihei HI") == "low"

def test_stopwords_ignored():
    # "The" / "of" / "Maui" are stopwords; "kihei coffee" tokens carry the match
    assert name_match_confidence("The Coffee of Maui", "Kihei Coffee shop") == "high"

def test_empty_name_is_low():
    assert name_match_confidence("", "anything") == "low"

from outreach.socials import find_social
from outreach.models import Business

class FakeResp:
    def __init__(self, payload, raise_exc=None):
        self._payload = payload
        self._raise = raise_exc
    def raise_for_status(self):
        if self._raise:
            raise self._raise
    def json(self):
        return self._payload

def make_get(payload, raise_exc=None):
    def _get(url, params=None, timeout=None):
        return FakeResp(payload, raise_exc)
    return _get

BIZ = Business(place_id="s1", name="Da Green Coffee Bar", town="Kihei")

def test_find_social_instagram_high():
    payload = {"items": [
        {"link": "https://www.instagram.com/dagreencoffeebar/",
         "title": "Da Green Coffee Bar (@dagreencoffeebar) - Instagram"}]}
    url, plat, conf = find_social(BIZ, "k", "cx", get=make_get(payload))
    assert plat == "instagram"
    assert "instagram.com/dagreencoffeebar" in url
    assert conf == "high"

def test_find_social_facebook_fallback():
    payload = {"items": [
        {"link": "https://example.com/listing", "title": "x"},
        {"link": "https://www.facebook.com/dagreencoffee", "title": "Da Green Coffee Bar"}]}
    url, plat, conf = find_social(BIZ, "k", "cx", get=make_get(payload))
    assert plat == "facebook"
    assert "facebook.com/dagreencoffee" in url

def test_find_social_low_confidence_on_mismatch():
    payload = {"items": [
        {"link": "https://www.instagram.com/someoneelse/", "title": "Maui Tacos Kihei"}]}
    url, plat, conf = find_social(BIZ, "k", "cx", get=make_get(payload))
    assert plat == "instagram"
    assert conf == "low"

def test_find_social_empty_items():
    assert find_social(BIZ, "k", "cx", get=make_get({"items": []})) == (None, None, "none")

def test_find_social_http_error():
    g = make_get({}, raise_exc=Exception("boom"))
    assert find_social(BIZ, "k", "cx", get=g) == (None, None, "none")

def test_find_social_missing_keys():
    assert find_social(BIZ, "", "cx", get=make_get({"items": []})) == (None, None, "none")
    assert find_social(BIZ, "k", "", get=make_get({"items": []})) == (None, None, "none")

def test_find_social_instagram_wins_when_both_present():
    # IG-first: Instagram is preferred even when Facebook is listed first.
    payload = {"items": [
        {"link": "https://www.facebook.com/dagreencoffee", "title": "Da Green Coffee Bar"},
        {"link": "https://www.instagram.com/dagreencoffeebar/", "title": "Da Green Coffee Bar"}]}
    url, plat, conf = find_social(BIZ, "k", "cx", get=make_get(payload))
    assert plat == "instagram"
    assert "instagram.com/dagreencoffeebar" in url

import time
import requests
from .models import Business

PLACES_URL = "https://places.googleapis.com/v1/places:searchText"
FIELD_MASK = (
    "places.id,places.displayName,places.formattedAddress,"
    "places.nationalPhoneNumber,places.websiteUri,places.rating,"
    "places.userRatingCount,places.businessStatus,nextPageToken"
)

def parse_places_response(data, town, category):
    out = []
    for p in data.get("places", []):
        if p.get("businessStatus") not in (None, "OPERATIONAL"):
            continue
        out.append(Business(
            place_id=p.get("id", ""),
            name=(p.get("displayName") or {}).get("text", ""),
            category=category,
            town=town,
            address=p.get("formattedAddress", ""),
            phone=p.get("nationalPhoneNumber", ""),
            website=p.get("websiteUri", ""),
            rating=float(p.get("rating", 0.0) or 0.0),
            review_count=int(p.get("userRatingCount", 0) or 0),
            business_status=p.get("businessStatus", "OPERATIONAL"),
        ))
    return out

def search(town, category, api_key, max_pages=2, timeout=10, _post=None):
    post = _post or requests.post
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": FIELD_MASK,
    }
    results, page_token = [], None
    for _ in range(max_pages):
        body = {"textQuery": f"{category} in {town}, Maui HI"}
        if page_token:
            body["pageToken"] = page_token
        r = post(PLACES_URL, headers=headers, json=body, timeout=timeout)
        r.raise_for_status()
        data = r.json()
        results.extend(parse_places_response(data, town, category))
        page_token = data.get("nextPageToken")
        if not page_token:
            break
        time.sleep(2)  # Places requires a short delay before nextPageToken works
    return results

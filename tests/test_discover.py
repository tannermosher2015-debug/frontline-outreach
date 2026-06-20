from outreach.discover import parse_places_response

SAMPLE = {
  "places": [
    {"id": "p1", "displayName": {"text": "Joe's Tacos"},
     "formattedAddress": "123 Main, Kihei", "nationalPhoneNumber": "(808) 555-1212",
     "rating": 4.1, "userRatingCount": 8, "businessStatus": "OPERATIONAL"},
    {"id": "p2", "displayName": {"text": "Modern Co"},
     "websiteUri": "https://modern.co", "rating": 4.9, "userRatingCount": 320,
     "businessStatus": "OPERATIONAL"},
    {"id": "p3", "displayName": {"text": "Closed Cafe"},
     "businessStatus": "CLOSED_PERMANENTLY"},
  ]
}

def test_parse_maps_fields_and_drops_closed():
    out = parse_places_response(SAMPLE, town="Kihei", category="restaurants")
    ids = [b.place_id for b in out]
    assert ids == ["p1", "p2"]                 # closed one dropped
    joe = out[0]
    assert joe.name == "Joe's Tacos"
    assert joe.phone == "(808) 555-1212"
    assert joe.website == ""
    assert joe.review_count == 8
    assert joe.town == "Kihei"
    assert joe.category == "restaurants"

def test_parse_empty():
    assert parse_places_response({}, "Kihei", "x") == []

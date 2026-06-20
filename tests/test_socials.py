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

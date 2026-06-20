from outreach.score import score_findings, primary_problem
from outreach.models import Findings

WEIGHTS = {"no_website": 30, "social_only": 25, "outdated_website": 20,
           "bad_mobile": 20, "no_contact_button": 15, "weak_google": 15,
           "no_service_pages": 10, "broken_links": 10, "old_photos": 5}

def test_score_sums_and_caps_at_100():
    f = Findings(no_website=True, social_only=True, weak_google=True,
                 bad_mobile=True, outdated_website=True)  # 30+25+15+20+20 = 110 -> 100
    score, summary = score_findings(f, WEIGHTS)
    assert score == 100
    assert "website" in summary.lower()

def test_score_partial():
    f = Findings(no_contact_button=True, weak_google=True)  # 15+15
    score, _ = score_findings(f, WEIGHTS)
    assert score == 30

def test_primary_problem_is_highest_weighted():
    f = Findings(no_contact_button=True, no_website=True)   # no_website weight 30 wins
    assert primary_problem(f, WEIGHTS) == "no_website"

def test_zero_findings():
    score, summary = score_findings(Findings(), WEIGHTS)
    assert score == 0
    assert summary == "No issues detected"

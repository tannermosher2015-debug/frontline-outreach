LABELS = {
    "no_website": "no website",
    "social_only": "social media only",
    "site_unreachable": "website is down",
    "weak_google": "weak Google presence",
    "no_contact_button": "no contact button",
    "no_service_pages": "no service pages",
    "outdated_website": "outdated website",
    "bad_mobile": "not mobile-friendly",
    "broken_links": "broken links",
    "old_photos": "old photos",
}

def score_findings(findings, weights):
    fired = findings.fired()
    raw = sum(weights.get(s, 0) for s in fired)
    score = min(100, raw)
    if not fired:
        return 0, "No issues detected"
    summary = " - ".join(LABELS.get(s, s) for s in fired)
    return score, summary

def primary_problem(findings, weights):
    fired = findings.fired()
    if not fired:
        return ""
    return max(fired, key=lambda s: weights.get(s, 0))

from datetime import date
from . import store, discover, audit, score, draft
from .models import Lead


def discover_all(config, api_key):
    out = []
    for town in config["towns"]:
        for category in config["categories"]:
            out.extend(discover.search(town, category, api_key))
    return out


def audit_one(business, config, current_year=None):
    return audit.audit_business(business, config, current_year=current_year)


def run_daily(conn, config, api_key, run_date=None):
    run_date = run_date or date.today().isoformat()
    weights = config["weights"]

    candidates = discover_all(config, api_key)
    # de-dupe within the run by place_id, then drop already-seen
    seen_ids, unique = set(), []
    for b in candidates:
        if b.place_id and b.place_id not in seen_ids:
            seen_ids.add(b.place_id); unique.append(b)
    fresh = store.filter_unseen(conn, unique)

    leads = []
    for b in fresh:
        findings = audit_one(b, config)
        sc, summary = score.score_findings(findings, weights)
        if sc <= 0:
            continue
        channel, subject, body = draft.build_draft(b, findings, weights)
        leads.append(Lead(business=b, findings=findings, score=sc, summary=summary,
                          channel=channel, subject=subject, draft=body))

    leads.sort(key=lambda l: l.score, reverse=True)
    leads = leads[: config["batch_size"]]
    for l in leads:
        store.save_lead(conn, l, run_date)
    return leads

from datetime import date
from . import store, discover, audit, score, draft, socials
from .models import Lead


def discover_all(config, api_key):
    out = []
    for town in config["towns"]:
        for category in config["categories"]:
            out.extend(discover.search(town, category, api_key))
    return out


def audit_one(business, config, current_year=None):
    return audit.audit_business(business, config, current_year=current_year)


def social_lookup_one(business, config):
    scfg = config.get("socials", {})
    if not scfg.get("enabled"):
        return
    from .config import get_env
    api_key = get_env("GOOGLE_CSE_KEY")
    cx = get_env("GOOGLE_CSE_CX")
    url, platform, conf = socials.find_social(
        business, api_key, cx,
        query_suffix=scfg.get("query_suffix", "instagram"),
        threshold=scfg.get("confidence_threshold", 0.6))
    if url:
        if platform == "instagram":
            business.instagram = url
        else:
            business.facebook = url
        business.social_confidence = conf


def run_daily(conn, config, api_key, run_date=None):
    run_date = run_date or date.today().isoformat()
    weights = config["weights"]

    candidates = discover_all(config, api_key)
    seen_ids, unique = set(), []
    for b in candidates:
        if b.place_id and b.place_id not in seen_ids:
            seen_ids.add(b.place_id); unique.append(b)
    fresh = store.filter_unseen(conn, unique)

    scored = []
    for b in fresh:
        findings = audit_one(b, config)
        sc, summary = score.score_findings(findings, weights)
        if sc <= 0:
            continue
        scored.append((b, findings, sc, summary))

    scored.sort(key=lambda t: t[2], reverse=True)
    top = scored[: config["batch_size"]]

    leads = []
    for b, findings, sc, summary in top:
        has_real_site = bool(b.website) and not audit.is_social_url(b.website)
        if not has_real_site and not (b.instagram or b.facebook):
            social_lookup_one(b, config)
        channel, subject, body = draft.build_draft(b, findings, weights)
        lead = Lead(business=b, findings=findings, score=sc, summary=summary,
                    channel=channel, subject=subject, draft=body)
        leads.append(lead)
        store.save_lead(conn, lead, run_date)
    return leads

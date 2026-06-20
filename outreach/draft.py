from .messages import DM_TEMPLATES, EMAIL_SUBJECTS, EMAIL_SIGNATURE, EMAIL_OPTOUT
from .score import primary_problem

def choose_channel(business):
    if business.email:
        return "email"
    if business.instagram or business.facebook:
        return "dm"
    if business.phone:
        return "phone"
    return "none"

def _template_key(findings, weights):
    p = primary_problem(findings, weights)
    return p if p in DM_TEMPLATES else "default"

def build_draft(business, findings, weights):
    channel = choose_channel(business)
    key = _template_key(findings, weights)
    body = DM_TEMPLATES[key].format(name=business.name)

    if channel == "email":
        subject = EMAIL_SUBJECTS.get(key, EMAIL_SUBJECTS["default"]).format(name=business.name)
        body = body + EMAIL_SIGNATURE + EMAIL_OPTOUT
        return channel, subject, body
    if channel == "phone":
        # A spoken script; same copy works read aloud.
        return channel, "", body
    return channel, "", body  # dm

"""Read inbox replies and route leads by intent.

yes -> lead marked `interested` (queued for a sample build + send)
no / stop / unsubscribe -> email suppressed instantly, lead `unsubscribed`
anything unclear -> left UNREAD in the inbox and marked `replied` for a human

Intent is read from the reply's NEW text only (quoted history is stripped first),
so our own words in the quote can't trigger a false positive. Unknown senders are
never touched. This module never sends or deletes; it only reads and flags \\Seen.
"""
import email
import imaplib
import re
from email.utils import parseaddr
from . import store

# Explicit opt-out phrases (checked first; a bare "no" is intentionally NOT here,
# because "no problem" / "no worries" are positive — those fall through to a human).
NEG = ("unsubscribe", "not interested", "no thanks", "no thank you", "stop",
       "remove me", "take me off", "opt out", "opt-out", "leave me alone")
# Clear go-aheads.
POS = ("yes", "sure", "sounds good", "interested", "send it", "send me",
       "go ahead", "let's do", "lets do", "i'd like", "id like", "please do",
       "would love", "let me see", "let's see", "lets see", "okay", "ok",
       "absolutely", "definitely")

_QUOTE = re.compile(r"^\s*>|^-{2,}\s*original message|on .+wrote:", re.I | re.M)

def top_post(text):
    """Return only the reply written above any quoted history."""
    if not text:
        return ""
    m = _QUOTE.search(text)
    return text[:m.start()] if m else text

def _has(t, keys):
    return any(re.search(r"\b" + re.escape(k) + r"\b", t) for k in keys)

def classify(text):
    t = top_post(text).lower()
    if _has(t, NEG):
        return "no"
    if _has(t, POS):
        return "yes"
    return "unclear"

def _body_text(msg):
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                try:
                    return part.get_payload(decode=True).decode(
                        part.get_content_charset() or "utf-8", "replace")
                except Exception:
                    continue
        return ""
    try:
        return msg.get_payload(decode=True).decode(
            msg.get_content_charset() or "utf-8", "replace")
    except Exception:
        return msg.get_payload() or ""

def poll_replies(conn, host, user, password, port=993, mailbox="INBOX"):
    """Classify UNSEEN replies from known leads and act. Returns a count summary.
    Unknown senders and unclear replies are left unread for the operator."""
    summary = {"interested": 0, "suppressed": 0, "unclear": 0, "unknown": 0}
    M = imaplib.IMAP4_SSL(host, int(port))
    M.login(user, password)
    try:
        M.select(mailbox)
        typ, data = M.search(None, "UNSEEN")
        if typ != "OK":
            return summary
        for num in data[0].split():
            typ, raw = M.fetch(num, "(RFC822)")
            if typ != "OK" or not raw or not raw[0]:
                continue
            msg = email.message_from_bytes(raw[0][1])
            from_email = parseaddr(msg.get("From", ""))[1].lower()
            lead = store.find_by_email(conn, from_email)
            if not lead:
                summary["unknown"] += 1
                continue  # a stranger's email; leave it unread and untouched
            verdict = classify(_body_text(msg))
            if verdict == "no":
                store.add_suppression(conn, from_email, "reply opt-out")
                store.set_status(conn, lead["place_id"], "unsubscribed")
                M.store(num, "+FLAGS", "\\Seen")
                summary["suppressed"] += 1
            elif verdict == "yes":
                store.set_status(conn, lead["place_id"], "interested")
                M.store(num, "+FLAGS", "\\Seen")
                summary["interested"] += 1
            else:
                # Don't downgrade a lead that's already further along.
                if lead["status"] in ("new", "contacted", "replied"):
                    store.set_status(conn, lead["place_id"], "replied")
                summary["unclear"] += 1  # left unread on purpose
        return summary
    finally:
        try:
            M.logout()
        except Exception:
            pass

def _demo():
    assert classify("Yes, please send it!") == "yes"
    assert classify("Sure, I'd like to see it") == "yes"
    assert classify("No thanks, not interested") == "no"
    assert classify("Please remove me from your list") == "no"
    assert classify("What's the catch?") == "unclear"
    assert classify("No problem, go ahead and send it") == "yes"  # not a false "no"
    # our own quoted words must not trigger yes:
    q = "Hmm, maybe.\n\nOn Mon, Tanner wrote:\n> free website sample, would you like? yes"
    assert classify(q) == "unclear", classify(q)
    # word boundaries: "eyes"/"book" must not match "yes"/"ok"
    assert classify("Keep your eyes on the book") == "unclear"
    print("replies self-check ok")

if __name__ == "__main__":
    _demo()

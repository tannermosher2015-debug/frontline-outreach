import argparse
import sys
import webbrowser
from datetime import date
from . import config as cfgmod
from . import store, pipeline

def build_parser():
    p = argparse.ArgumentParser(prog="outreach", description="Frontline Outreach lead tool")
    sub = p.add_subparsers(dest="command", required=True)
    pr = sub.add_parser("run", help="Build today's lead batch")
    pr.add_argument("--date", default=None)
    pr.add_argument("--config", default="config.toml")
    ps = sub.add_parser("serve", help="Open the review dashboard")
    ps.add_argument("--config", default="config.toml")
    ps.add_argument("--port", type=int, default=5000)
    pd = sub.add_parser("send", help="Process approved email leads (respects send_mode)")
    pd.add_argument("--config", default="config.toml")
    pd.add_argument("--date", default=None)
    prp = sub.add_parser("replies", help="Read inbox replies and route leads (yes/no/unclear)")
    prp.add_argument("--config", default="config.toml")
    pss = sub.add_parser("send-samples", help="Email sample + deposit link to interested leads that have a built sample")
    pss.add_argument("--config", default="config.toml")
    pq = sub.add_parser("queue", help="List interested leads that still need a sample built")
    pq.add_argument("--config", default="config.toml")
    pset = sub.add_parser("set-sample", help="Record a built demo URL for a lead (marks it ready to send)")
    pset.add_argument("place_id")
    pset.add_argument("url")
    pset.add_argument("--config", default="config.toml")
    pfu = sub.add_parser("send-followups", help="Send one gentle follow-up to leads who never replied")
    pfu.add_argument("--config", default="config.toml")
    return p

def cmd_run(ns):
    cfg = cfgmod.load_config(ns.config)
    api_key = cfgmod.get_env("PLACES_API_KEY")
    if not api_key:
        print("PLACES_API_KEY not set (.env). Aborting.", file=sys.stderr); return 1
    conn = store.connect(cfg["db_path"]); store.init_db(conn)
    leads = pipeline.run_daily(conn, cfg, api_key, run_date=ns.date)
    print(f"Built {len(leads)} leads for {ns.date or date.today().isoformat()}.")
    for l in leads:
        print(f"  [{l.score:3}] {l.business.name} - {l.channel} - {l.summary}")
    return 0

def cmd_serve(ns):
    from .server import create_app
    cfg = cfgmod.load_config(ns.config)
    store.init_db(store.connect(cfg["db_path"]))
    app = create_app(cfg, api_key=cfgmod.get_env("RESEND_API_KEY", ""))
    url = f"http://127.0.0.1:{ns.port}/"
    print(f"Dashboard at {url}")
    webbrowser.open(url)
    app.run(port=ns.port)
    return 0

def cmd_send(ns):
    from . import send as sender
    cfg = cfgmod.load_config(ns.config)
    api_key = cfgmod.get_env("RESEND_API_KEY", "")
    conn = store.connect(cfg["db_path"]); store.init_db(conn)
    run_date = ns.date or date.today().isoformat()
    n = 0
    for row in store.todays_batch(conn, run_date):
        if row["channel"] == "email" and row["status"] == "new":
            res = sender.send_email_lead(conn, row["place_id"], cfg, api_key, run_date)
            print(f"  {row['name']}: {res['mode']}")
            n += 1
    print(f"Processed {n} email leads (mode={cfg.get('send_mode')}).")
    return 0

def cmd_replies(ns):
    from . import replies
    cfg = cfgmod.load_config(ns.config)
    user = cfgmod.get_env("IMAP_USER")
    password = cfgmod.get_env("IMAP_PASS")
    if not (user and password):
        print("IMAP_USER / IMAP_PASS not set in .env. Aborting.", file=sys.stderr); return 1
    host = cfgmod.get_env("IMAP_HOST", "imap.hostinger.com")
    port = cfgmod.get_env("IMAP_PORT", "993")
    mailbox = cfg.get("replies", {}).get("mailbox", "INBOX")
    conn = store.connect(cfg["db_path"]); store.init_db(conn)
    summary = replies.poll_replies(conn, host, user, password, port=port, mailbox=mailbox)
    print(f"Replies processed: {summary}")
    return 0

def cmd_send_samples(ns):
    from . import send as sender
    cfg = cfgmod.load_config(ns.config)
    api_key = cfgmod.get_env("RESEND_API_KEY", "")
    conn = store.connect(cfg["db_path"]); store.init_db(conn)
    leads = store.leads_awaiting_sample_send(conn)
    for lead in leads:
        res = sender.send_sample_email(conn, lead["place_id"], cfg, api_key)
        print(f"  {lead['name']}: {res['mode']}")
    print(f"Processed {len(leads)} sample sends (mode={cfg.get('send_mode')}).")
    return 0

def cmd_queue(ns):
    cfg = cfgmod.load_config(ns.config)
    conn = store.connect(cfg["db_path"]); store.init_db(conn)
    leads = store.leads_awaiting_build(conn)
    for l in leads:
        site = l["website"] or l["instagram"] or l["facebook"] or "(no site)"
        print(f"  {l['place_id']}  {l['name']} | {l['category']}, {l['town']} | {site}")
    print(f"{len(leads)} lead(s) awaiting a built sample.")
    return 0

def cmd_set_sample(ns):
    cfg = cfgmod.load_config(ns.config)
    conn = store.connect(cfg["db_path"]); store.init_db(conn)
    store.set_sample_url(conn, ns.place_id, ns.url.strip())
    print(f"Sample URL set for {ns.place_id}: {ns.url.strip()}")
    print("Next: python -m outreach send-samples  (respects send_mode)")
    return 0

def cmd_send_followups(ns):
    from . import send as sender
    cfg = cfgmod.load_config(ns.config)
    api_key = cfgmod.get_env("RESEND_API_KEY", "")
    conn = store.connect(cfg["db_path"]); store.init_db(conn)
    today = date.today().isoformat()
    cap = cfg.get("daily_email_cap", 10)
    remaining = max(0, cap - store.emails_sent_on(conn, today) - store.followups_sent_on(conn, today))
    if remaining <= 0:
        print("Daily email budget already used; no follow-ups sent."); return 0
    days = cfg.get("followup_after_days", 4)
    leads = store.leads_awaiting_followup(conn, days)[:remaining]
    for lead in leads:
        res = sender.send_followup_email(conn, lead["place_id"], cfg, api_key)
        print(f"  {lead['name']}: {res['mode']}")
    print(f"Processed {len(leads)} follow-up(s) (mode={cfg.get('send_mode')}, budget left {remaining}).")
    return 0

def main(argv=None):
    ns = build_parser().parse_args(argv)
    return {"run": cmd_run, "serve": cmd_serve, "send": cmd_send,
            "replies": cmd_replies, "send-samples": cmd_send_samples,
            "queue": cmd_queue, "set-sample": cmd_set_sample,
            "send-followups": cmd_send_followups}[ns.command](ns)

if __name__ == "__main__":
    raise SystemExit(main())

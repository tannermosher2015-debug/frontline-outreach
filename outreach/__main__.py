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

def main(argv=None):
    ns = build_parser().parse_args(argv)
    return {"run": cmd_run, "serve": cmd_serve, "send": cmd_send}[ns.command](ns)

if __name__ == "__main__":
    raise SystemExit(main())

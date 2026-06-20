import json
from datetime import date
from flask import Flask, render_template, request, jsonify
from . import store, send

def create_app(config, conn=None, today=None, api_key=""):
    app = Flask(__name__, template_folder="web/templates", static_folder="web/static")
    today = today or date.today().isoformat()
    _conn = conn or store.connect(config["db_path"])

    def rows():
        out = []
        for r in store.todays_batch(_conn, today):
            r["problems"] = json.loads(r["findings"] or "[]")
            out.append(r)
        return out

    @app.route("/")
    def dashboard():
        leads = rows()
        sent = sum(1 for r in leads if r["status"] == "contacted")
        return render_template("dashboard.html", leads=leads, today=today,
                               sent=sent, total=len(leads))

    @app.route("/history")
    def history():
        return render_template("history.html", rows=store.history(_conn))

    @app.route("/action/skip", methods=["POST"])
    def skip():
        store.set_status(_conn, request.json["place_id"], "skipped")
        return jsonify(ok=True)

    @app.route("/action/contacted", methods=["POST"])
    def contacted():
        d = request.json
        store.mark_contacted(_conn, d["place_id"], d.get("channel", "manual"))
        return jsonify(ok=True)

    @app.route("/action/edit", methods=["POST"])
    def edit():
        d = request.json
        store.update_draft(_conn, d["place_id"], d["draft_text"])
        return jsonify(ok=True)

    @app.route("/action/send", methods=["POST"])
    def send_action():
        res = send.send_email_lead(_conn, request.json["place_id"], config,
                                   api_key=api_key, run_date=today)
        return jsonify(res)

    return app

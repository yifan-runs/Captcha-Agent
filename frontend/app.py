from flask import Flask, render_template, request, jsonify
import json
import os
import time

app = Flask(__name__)

LOG_FILE = os.path.join(os.path.dirname(__file__), "fingerprint_log.json")


# ---------- helpers ----------

def load_logs():
    """Load all fingerprint log entries as a list."""
    if not os.path.exists(LOG_FILE):
        return []
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        else:
            # In case someone wrote a single object by mistake
            return [data]
    except Exception:
        return []


# ---------- main routes ----------

@app.route("/")
def login():
    return render_template("index.html")


@app.route("/captcha")
def captcha():
    return render_template("captcha.html")


@app.route("/log_fingerprint", methods=["POST"])
def log_fingerprint():
    data = request.get_json(force=True) or {}

    # Basic metadata
    ip = request.remote_addr or "unknown"
    session_id = data.get("session_id") or "unknown"
    now = time.time()

    events = data.get("events", [])
    features = data.get("features", {})
    classification = data.get("classification", {}) or {}

    captcha_passed = data.get("captcha_passed")
    final_allowed = data.get("final_allowed")
    attempt_index = data.get("attempt_index")

    is_human = classification.get("is_human")
    risk_score = classification.get("risk_score", 0)

    entry = {
        "ip": ip,
        "session_id": session_id,
        "timestamp": now,

        "captcha_passed": captcha_passed,
        "final_allowed": final_allowed,
        "attempt_index": attempt_index,

        "is_human": is_human,
        "risk_score": risk_score,

        "features": features,
        "classification": classification,
        "events": events,
    }

    logs = load_logs()
    logs.append(entry)

    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(logs, f, indent=2)

    return jsonify({"status": "ok"})


# ---------- admin pages / APIs ----------

@app.route("/admin")
def admin():
    # Renders the admin dashboard page (HTML + JS)
    return render_template("admin.html")


@app.route("/api/summary")
def api_summary():
    """
    Return aggregate statistics from fingerprint_log.json
    used for the top-level cards on the dashboard.
    """
    logs = load_logs()
    total_runs = len(logs)

    total_captcha_passed = sum(1 for e in logs if e.get("captcha_passed") is True)
    total_final_allowed = sum(1 for e in logs if e.get("final_allowed") is True)

    human_runs = sum(1 for e in logs if e.get("is_human") is True)
    bot_runs = sum(1 for e in logs if e.get("is_human") is False)

    suspicious_runs = 0
    for e in logs:
        cls = e.get("classification") or {}
        if cls.get("suspicious") is True:
            suspicious_runs += 1

    unique_ips = len({e.get("ip", "unknown") for e in logs})

    return jsonify({
        "total_runs": total_runs,
        "total_captcha_passed": total_captcha_passed,
        "total_final_allowed": total_final_allowed,
        "human_runs": human_runs,
        "bot_runs": bot_runs,
        "suspicious_runs": suspicious_runs,
        "unique_ips": unique_ips,
    })


@app.route("/api/sessions")
def api_sessions():
    """
    Return a list of recent sessions (for the table).
    Optional query params:
      - limit: how many rows (default 100)
      - ip: filter by IP (optional)
      - verdict: 'allowed', 'blocked', or 'all' (optional)
    """
    logs = load_logs()

    # sort newest first
    logs = sorted(logs, key=lambda e: e.get("timestamp", 0), reverse=True)

    # filters
    ip_filter = request.args.get("ip")
    verdict_filter = request.args.get("verdict", "all")  # allowed / blocked / all
    try:
        limit = int(request.args.get("limit", "100"))
    except ValueError:
        limit = 100

    def compute_verdict(entry):
        if entry.get("final_allowed"):
            return "allowed"
        elif entry.get("captcha_passed"):
            # Solved puzzle but blocked by behaviour (bot-like)
            return "blocked_suspicious"
        else:
            # Failed the puzzle itself
            return "blocked_failed"
    
    rows = []
    for e in logs:
        v = compute_verdict(e)

        if ip_filter and e.get("ip") != ip_filter:
            continue
        if verdict_filter != "all":
            if verdict_filter == "allowed" and v != "allowed":
                continue
            if verdict_filter == "blocked" and v == "allowed":
                continue

        rows.append({
            "timestamp": e.get("timestamp"),
            "ip": e.get("ip", "unknown"),
            "session_id": e.get("session_id", "unknown"),
            "captcha_passed": e.get("captcha_passed"),
            "final_allowed": e.get("final_allowed"),
            "is_human": e.get("is_human"),
            "risk_score": e.get("risk_score", 0),
            "attempt_index": e.get("attempt_index"),
            "verdict": v,
        })

        if len(rows) >= limit:
            break

    return jsonify({"sessions": rows})


if __name__ == "__main__":
    app.run(debug=True)

from flask import Flask, render_template, request, jsonify
import json
import os
import time

app = Flask(__name__)

LOG_FILE = os.path.join(os.path.dirname(__file__), "fingerprint_log.json")


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
    # For now we don't have a real session cookie – you can add later
    session_id = data.get("session_id") or "unknown"
    now = time.time()

    events = data.get("events", [])
    features = data.get("features", {})
    classification = data.get("classification", {}) or {}

    captcha_passed = data.get("captcha_passed")
    final_allowed = data.get("final_allowed")
    attempt_index = data.get("attempt_index")

    is_human = classification.get("is_human")
    risk_score = classification.get("risk_score")

    # One log entry = one CAPTCHA run
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

    # Append to JSON list file
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                logs = json.load(f)
            if not isinstance(logs, list):
                logs = [logs]
        except Exception:
            logs = []
    else:
        logs = []

    logs.append(entry)

    with open(LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(logs, f, indent=2)

    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=True)

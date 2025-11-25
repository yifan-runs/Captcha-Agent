from flask import Flask, render_template, request, jsonify
import json
import os

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
    data = request.get_json(force=True)

    entry = {
        "events": data.get("events", []),
        "features": data.get("features", {}),
        "classification": data.get("classification", {}),
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
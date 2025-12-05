#!/bin/bash
set -e

SERVER_PID=""
cleanup() {
    if [[ -n "$SERVER_PID" ]]; then
        kill "$SERVER_PID" 2>/dev/null || true
    fi
}

trap cleanup EXIT INT TERM

echo "=== Starting local server ==="

if [ -f './frontend/app.py' ]; then
    python ./frontend/app.py &
    SERVER_PID=$!
    sleep 3
else
    echo "app.py not found!"
fi

echo "=== Running VLM Attacker ==="
echo ">>> Make sure the server URL is correctly set up"
echo ">>> Make sure the ollama URL is correctly set up"
python ./vlm.py

echo "=== Done ==="
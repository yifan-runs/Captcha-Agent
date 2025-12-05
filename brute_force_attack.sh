#!/bin/bash
set -e

echo "=== Running setup script ==="

# 1. Run installation script
if [ -f install.sh ]; then
    echo "Executing install.sh..."
    bash ./brute_force_attacker/install.sh
else
    echo "install.sh not found!"
fi

echo "=== Starting local server ==="

# 2. Start your application server
if [ -f app.py ]; then
    python ./brute_force_attacker/frontend2/app.py &
    SERVER_PID=$!
    sleep 3
else
    echo "app.py not found!"
fi

echo "=== Running main logic script ==="

# 3. Run main program
python ./brute_force_attacker/run_attacker.py

if [ ! -z "$SERVER_PID" ]; then
    kill $SERVER_PID
fi

echo "=== Done ==="

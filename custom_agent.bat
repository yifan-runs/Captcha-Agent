@echo off
echo [INFO] Starting CAPTCHA frontend in a new PowerShell window...

start powershell -NoExit -Command "python frontend/app.py"

echo.
echo ==============================================
echo Frontend is running in a new terminal window.
echo Press ENTER to start the custom agent.
echo ==============================================
pause

echo [INFO] Starting custom agent...
python frontend/trigger_custom_agent.py

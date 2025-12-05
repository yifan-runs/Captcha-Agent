# scalable_project2

This repository contains a simple interactive bubble CAPTCHA and a custom agent designed to attempt solving it.  

---

## **Running the CAPTCHA on a Raspberry Pi (RPi)**

1. **Connect to TCD VPN**  
- tailscale login --login-server https://vpn-student.scss.tcd.ie

2. **SSH to the jump host**
- ssh your-username@macneill.tcd.ie

3. **SSH to the RPi and set up port forwarding**
Example (for local port 8080 forwarded to RPi port 3000):
- ssh -L 8080:localhost:3000 -J your-username@macneill.tcd.ie your-username@rasp-021.berry.scss.tcd.ie

4. **Run the CAPTCHA frontend**
- python frontend/app.py

The CAPTCHA should now be accessible via http://localhost:8080 on your local machine.

## **Running the Custom Agent Locally**
Assuming the CAPTCHA is accessible via the tunneled port (e.g., 8080):

---

- python trigger_custom_agent.py

The agent will connect to the CAPTCHA, track the bubbles, and attempt to solve the task automatically.

## Note:
- Make sure Python dependencies are installed for both the CAPTCHA frontend and the agent.

- Adjust tunneling ports as needed if 8080 is already in use.

- The custom agent uses OCR and mouse automation to interact with the CAPTCHA, so ensure the required libraries (pyautogui, pytesseract, opencv-python, etc.) are installed.

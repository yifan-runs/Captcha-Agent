# scalable_project2

This repository contains a simple interactive bubble CAPTCHA and a custom agent designed to attempt solving it.  

Use respective .sh or .bat files to run individual agents:
- .\custom_agent.bat
- .\brute_force_attack.sh

or follow the following instructions:
---

## **Connecting to Raspberry Pi (RPi) to run frontend (OPTIONAL)**

1. **Connect to TCD VPN**  
- tailscale login --login-server https://vpn-student.scss.tcd.ie

2. **SSH to the jump host**
- ssh your-username@macneill.tcd.ie

3. **SSH to the RPi and set up port forwarding**
Example (for local port 3000 forwarded to RPi port 3000):
- ssh -L 3000:localhost:3000 -J your-username@macneill.tcd.ie your-username@rasp-021.berry.scss.tcd.ie

## **Running the CAPTCHA**

**Run the CAPTCHA frontend (locally or on RPi)**
- python frontend/app.py
Assuming 'frontend' folder has already been added to RPi
The CAPTCHA should now be accessible via http://localhost:3000 on your local machine.

## **Custom Agent Attacker**

This Agent is custom built for this CAPTCHA and uses fully local elements to function.

Assuming the CAPTCHA is accessible via port 3000:

---

- python frontend/trigger_custom_agent.py

The agent will connect to the CAPTCHA, track the bubbles, and attempt to solve the task automatically.

## Note:
- Make sure Python dependencies are installed for both the CAPTCHA frontend and the agent.

- Adjust tunneling ports as needed if 8080 is already in use.

- The custom agent uses OCR and mouse automation to interact with the CAPTCHA, so ensure the required libraries (pyautogui, pytesseract, opencv-python, etc.) are installed.

## Brute Force Attacker

This project is an automated testing script based on **Python + Selenium + Chromium**, designed for:

* Performing automated interaction testing on **CAPTCHA pages that we have built ourselves**
* Using multiple "brute force" style interaction strategies to test how the CAPTCHA component behaves under different interaction paths, and to verify whether the system’s response and protection logic are robust

**a. Install Dependencies**

    Make sure the following are installed:

    * Python 3.x
    * Selenium
    * Chromium / Chrome browser
    * Matching version of ChromeDriver

run install.sh

---

**b. Start Your Local CAPTCHA Page**

For example, if you run a Flask server:

```bash
python app.py
```

Make sure it can be accessed via:

```
http://127.0.0.1:3000/captcha
```

---

**c. Run the Script**

In the project directory, execute:

```bash
python run_attacker.py
```

The script will:

1. Start the browser
2. Open your local CAPTCHA page
3. Execute multiple interaction testing strategies
4. Save screenshots and logs
5. Safely close the browser

## **VLM attacker**

This is a simple script where a vision language model clicks on moving bubbles in a captcha.
The main file is `vlm.py`. run that file.

### How to start

1. Make sure you have python and pip installed  
2. Install python packages:

   ```bash
   pip install -r requirements.txt
   ```

3. Start your captcha server. it should show a page with a canvas (default url is `http://127.0.0.1:3000/captcha`)  
4. Start the ollama server (download from the ollama website), for example:

   ```bash
   ollama serve
   ```

5. Run the attacker:

   ```bash
   python vlm.py
   ```

The script will open the captcha in a headless browser, track bubbles, send frames to the vlm and then click.

### Change captcha url

In `vlm.py` there is this line:

```python
sp: SeleniumPortal = SeleniumPortal("http://127.0.0.1:3000/captcha")
```

change the url string to your own captcha page if it is different. for example:

```python
sp: SeleniumPortal = SeleniumPortal("http://my-server:3000/captcha")
```

### Change ollama url

in `vlm.py` there is this line:

```python
client = ollama.Client(host="http://127.0.0.1:11434", timeout=60)
```

if your ollama is on another host or port, change the `host` value. for example:

```python
client = ollama.Client(host="http://192.168.1.10:11434", timeout=60)
```

You can also change the model name in `MODEL_NAME` if you want another vision model.

### Change ROI for the tracker

ROI (region of interest) tells the tracker which part of the screen to look at. so it does not look at other gui elements of the captcha.

in `vlm.py` the tracker thread is started like this:

```python
tracker_thread = threading.Thread(
    target=kalman_tracker_worker,
    args=(q, stop_ev),
    kwargs={
        "source": sp,
        "roi": (0.0, 0.18, 1.0, 0.95),
        "max_misses": 60,
        "put_timeout": 0.01,
        "show_window": True
    },
    daemon=True
)
```

The roi tuple is `(x0, y0, x1, y1)` in normalized coordinates:

- `0.0` means left or top edge of the frame  
- `1.0` means right or bottom edge of the frame  

so:

- `x0` = left of roi  
- `y0` = top of roi  
- `x1` = right of roi  
- `y1` = bottom of roi  

If the tracker also sees text it may get distracted, so move these numbers so roi only covers the bubble area. for example, to ignore more of the top ui you can increase `y0`:

```python
"roi": (0.05, 0.25, 0.95, 0.9),
```

you just edit this line in `vlm.py` and run again.

---

- If the window that shows tracking is annoying you can set `"show_window": False` in the same kwargs block  
- Make sure the captcha url and ollama url are reachable from the machine where you run `vlm.py`
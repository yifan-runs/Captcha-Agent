#!/usr/bin/env python3
"""
custom_agent_browser.py

Agent that finds a browser window by title (substring), OCRs the HUD (canvas top),
tracks bubbles in the canvas area, and clicks the correct bubbles.

Usage:
 - Ensure the CAPTCHA page is open in a browser window whose title includes WINDOW_TITLE_SUBSTR.
 - Run this agent; it will detect the window, OCR the HUD and act.

Notes / tuning:
 - If the HUD or canvas are offset because of toolbars, change TITLE_BAR_ESTIMATE or HUD_LEFT/RIGHT margins.
 - For macOS the code uses Quartz to enumerate windows; on Windows/Linux it uses pygetwindow.
"""

import platform
import time
import threading
import math
import shutil
from collections import deque
from datetime import datetime

import pyautogui
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"  # adjust as needed
import numpy as np
import cv2

# optional: pygetwindow for Windows/Linux
try:
    import pygetwindow as gw
except Exception:
    gw = None

# macOS Quartz window listing
if platform.system() == "Darwin":
    try:
        from Quartz import CGWindowListCopyWindowInfo, kCGWindowListOptionOnScreenOnly, kCGNullWindowID
    except Exception:
        CGWindowListCopyWindowInfo = None

# -------------------------
# Config
# -------------------------
WINDOW_TITLE_SUBSTR = "Bubble CAPTCHA"  # substring to search for in window titles (change to your page <title>)
HUD_HEIGHT = 56              # pixels in your canvas HUD (JS uses 56)
HUD_LEFT_MARGIN = 10
HUD_RIGHT_MARGIN = 10
PLAY_TOP_MARGIN = 12         # distance from HUD bottom to play area (approx)
PLAY_BOTTOM_MARGIN = 40      # footer area size in your game
TRACK_FPS = 15
CLICK_DELAY = 0.12
MAX_OCR_ATTEMPTS = 20

# Hough parameters (tweak if detection misses)
HOUGH_DP = 1.2
HOUGH_MIN_DIST = 30
HOUGH_PARAM1 = 50
HOUGH_PARAM2 = 28
HOUGH_MIN_RADIUS = 12
HOUGH_MAX_RADIUS = 90

COLOR_MAP = {
    "BLUE":   (80, 160, 255),
    "RED":    (230, 80, 80),
    "GREEN":  (80, 200, 120),
    "YELLOW": (240, 220, 80),
    "ORANGE": (245, 170, 80),
    # extend if needed...
}

# Shared runtime state
shared_state = {
    "instruction": None,    # { "text", "no_of_bubbles", "bubble_order" }
    "bubbles": [],          # tracked bubbles (absolute screen coords)
    "events": [],
    "running": True,
    "window_coords": None,
}

# -------------------------
# Utilities & logging
# -------------------------
def log_event(event_type, **kwargs):
    t = time.time()
    shared_state["events"].append({"time": t, "type": event_type, **kwargs})

def ensure_tesseract():
    """Try to ensure pytesseract.tesseract_cmd is set; if not, attempt to find tesseract."""
    if getattr(pytesseract.pytesseract, "tesseract_cmd", None):
        return
    if shutil.which("tesseract"):
        pytesseract.pytesseract.tesseract_cmd = shutil.which("tesseract")
        return
    # Windows common path fallback
    if platform.system() == "Windows":
        candidate = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        if shutil.os.path.exists(candidate):
            pytesseract.pytesseract.tesseract_cmd = candidate
            return
    raise FileNotFoundError("Tesseract executable not found. Install or set pytesseract.pytesseract.tesseract_cmd")

# -------------------------
# Window discovery by title substring
# -------------------------
def find_window_by_title_substr(substr=WINDOW_TITLE_SUBSTR, min_width=300, min_height=200):
    system = platform.system()
    if system in ("Windows", "Linux") and gw is not None:
        try:
            wins = gw.getWindowsWithTitle("")  # get all, then filter
            for w in wins:
                title = (w.title or "")
                if substr.lower() in title.lower() and w.width >= min_width and w.height >= min_height:
                    return {"x": w.left, "y": w.top, "width": w.width, "height": w.height, "title": title}
        except Exception as e:
            # fallback: gw may behave differently; try getAllWindows
            try:
                wins = gw.getAllWindows()
                for w in wins:
                    title = (w.title or "")
                    if substr.lower() in title.lower() and w.width >= min_width and w.height >= min_height:
                        return {"x": w.left, "y": w.top, "width": w.width, "height": w.height, "title": title}
            except Exception:
                pass
        return None
    elif system == "Darwin" and CGWindowListCopyWindowInfo is not None:
        # macOS: iterate windows and match kCGWindowName
        window_list = CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly, kCGNullWindowID)
        for w in window_list:
            name = w.get("kCGWindowName", "") or ""
            owner = w.get("kCGWindowOwnerName", "") or ""
            bounds = w.get("kCGWindowBounds", {}) or {}
            width = int(bounds.get("Width", 0))
            height = int(bounds.get("Height", 0))
            if substr.lower() in name.lower() or substr.lower() in owner.lower():
                if width >= min_width and height >= min_height:
                    return {"x": int(bounds.get("X", 0)), "y": int(bounds.get("Y", 0)), "width": width, "height": height, "title": name or owner}
        return None
    else:
        return None

# -------------------------
# OCR thread
# -------------------------
import re
def ocr_read_hud_thread(max_attempts=MAX_OCR_ATTEMPTS):
    ensure_tesseract()
    attempts = 0
    while attempts < max_attempts and shared_state["running"]:
        attempts += 1
        log_event("ocr_attempt", attempt=attempts)
        coords = shared_state.get("window_coords") or find_window_by_title_substr()
        if not coords:
            print(f"[OCR] window not found (attempt {attempts}/{max_attempts}). Retrying...")
            time.sleep(0.8)
            continue

        x, y, w, h = coords["x"], coords["y"], coords["width"], coords["height"]
        # Estimate titlebar height (varies by OS/browser). Allow user adjustment if needed.
        title_bar_height = 30 if platform.system() == "Windows" else 0
        hud_region = (
            int(x + 60),
            int(y + title_bar_height + 80),
            int(w - 120),
            int(100)
        )


        try:
            img = pyautogui.screenshot(region=hud_region)
        except Exception as e:
            print("[OCR] screenshot failed:", e)
            time.sleep(0.5)
            continue

        frame = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        # adaptive threshold or mild thresholding helps OCR on light backgrounds
        _, th = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
        text = pytesseract.image_to_string(th).strip()
        print("[OCR] reads:\n", text)
        log_event("ocr_text", raw=text)
        
        # --- SUCCESS DETECTION ---
        success_patterns = [
            r"captcha\s+passed",
            r"captcha\s+assed",          # handles the typo you observed
            r"you\s+may\s+proceed"
        ]

        lower_text = text.lower()
        if any(re.search(pat, lower_text) for pat in success_patterns):
            print("[OCR] CAPTCHA success detected — exiting agent.")
            log_event("captcha_success", raw=text)
            shared_state["running"] = False
            return None
        # --- END SUCCESS DETECTION ---


        # Try to find number and ordering word
        number_match = re.search(r"\b(2|3)\b", text)
        order_match = re.search(r"\b(ascending|descending)\b", text, re.IGNORECASE)
        if number_match and order_match:
            instr = {
                "text": text,
                "no_of_bubbles": int(number_match.group(1)),
                "bubble_order": order_match.group(1).lower()
            }
            shared_state["instruction"] = instr
            print("[OCR] Instruction extracted:", instr)
            log_event("ocr_success", instruction=instr)
            return instr

        print("[OCR] failed to parse instruction. retrying...")
        time.sleep(0.8)

    print("[OCR] giving up after attempts.")
    log_event("ocr_failed", attempts=attempts)
    return None

# -------------------------
# Bubble tracking (Hough) thread
# -------------------------
def color_name_from_bgr(bgr_pixel):
    b, g, r = int(bgr_pixel[0]), int(bgr_pixel[1]), int(bgr_pixel[2])
    best = None
    best_d = float("inf")
    for name, rgb in COLOR_MAP.items():
        dr = r - rgb[0]
        dg = g - rgb[1]
        db = b - rgb[2]
        d = dr*dr + dg*dg + db*db
        if d < best_d:
            best_d = d
            best = name
    return best

def bubble_tracking_thread():
    last_frame_bubbles = []
    next_id = 1
    # Wait for window coords
    while shared_state["running"] and shared_state.get("window_coords") is None:
        w = find_window_by_title_substr()
        if w:
            shared_state["window_coords"] = w
            print("[TRACK] detected window coords:", w)
            break
        time.sleep(0.4)

    coords = shared_state["window_coords"]
    if not coords:
        print("[TRACK] window not found; exiting tracker.")
        return

    x, y, w, h = coords["x"], coords["y"], coords["width"], coords["height"]
    title_bar_height = 30 if platform.system() == "Windows" else 0
    play_region = (
        int(x + 10),
        int(y + title_bar_height + HUD_HEIGHT + PLAY_TOP_MARGIN),
        int(w - 20),
        int(h - HUD_HEIGHT - PLAY_TOP_MARGIN - PLAY_BOTTOM_MARGIN)
    )
    print("[TRACK] play region:", play_region)
    log_event("track_start", play_region=play_region)

    capture_interval = 1.0 / TRACK_FPS
    while shared_state["running"]:
        t0 = time.time()
        try:
            img = pyautogui.screenshot(region=play_region)
        except Exception as e:
            print("[TRACK] screenshot error:", e)
            time.sleep(0.2)
            continue

        frame = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.medianBlur(gray, 5)

        circles = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, dp=HOUGH_DP, minDist=HOUGH_MIN_DIST,
                                   param1=HOUGH_PARAM1, param2=HOUGH_PARAM2,
                                   minRadius=HOUGH_MIN_RADIUS, maxRadius=HOUGH_MAX_RADIUS)
        frame_bubbles = []

        if circles is not None:
            circles = np.uint16(np.around(circles))
            for c in circles[0, :]:
                cx, cy, r = int(c[0]), int(c[1]), int(c[2])
                sx = min(max(cx, 0), frame.shape[1]-1)
                sy = min(max(cy, 0), frame.shape[0]-1)
                bgr = frame[sy, sx].tolist()
                color_name = color_name_from_bgr(bgr)
                frame_bubbles.append({"x": cx, "y": cy, "r": r, "color_name": color_name})

        # nearest neighbor assign ids
        assigned = []
        new_bubbles = []
        for fb in frame_bubbles:
            best_match = None
            best_d = float("inf")
            for lb in last_frame_bubbles:
                dx = fb["x"] - lb["x"]
                dy = fb["y"] - lb["y"]
                d = math.hypot(dx, dy)
                if d < 50 and d < best_d and not lb.get("assigned", False):
                    best_d = d
                    best_match = lb
            if best_match is not None:
                fb["id"] = best_match["id"]
                best_match["assigned"] = True
                assigned.append(fb)
            else:
                fb["id"] = None
                new_bubbles.append(fb)

        for nb in new_bubbles:
            nb["id"] = next_id
            next_id += 1

        current_bubbles = assigned + new_bubbles
        abs_bubbles = []
        for b in current_bubbles:
            abs_x = play_region[0] + b["x"]
            abs_y = play_region[1] + b["y"]
            abs_bubbles.append({
                "id": b["id"],
                "x": abs_x,
                "y": abs_y,
                "r": b["r"],
                "color_name": b["color_name"]
            })

        shared_state["bubbles"] = abs_bubbles
        log_event("track_frame", count=len(abs_bubbles))

        last_frame_bubbles = [{"id": b["id"], "x": b["x"], "y": b["y"]} for b in frame_bubbles]

        elapsed = time.time() - t0
        to_sleep = max(0.0, capture_interval - elapsed)
        time.sleep(to_sleep)

    log_event("track_stop")
    print("[TRACK] tracker exiting.")

# -------------------------
# Clicker
# -------------------------
def choose_targets_and_click():
    while shared_state["running"] and shared_state.get("instruction") is None:
        time.sleep(0.2)

    instr = shared_state.get("instruction")
    if not instr:
        print("[CLICKER] No instruction; exiting.")
        return

    needed = instr["no_of_bubbles"]
    order = instr["bubble_order"]
    print(f"[CLICKER] Instruction: burst {needed} bubbles in {order} order.")

    # Allow tracker to populate
    time.sleep(0.6)
    b_snapshot = list(shared_state.get("bubbles", []))
    if not b_snapshot:
        print("[CLICKER] no bubbles tracked; aborting.")
        return

    uniq = {}
    for b in b_snapshot:
        uniq[b["id"]] = b
    bubble_list = list(uniq.values())

    bubble_list.sort(key=lambda x: x["r"])
    if order == "ascending":
        targets = bubble_list[:needed]
    else:
        targets = bubble_list[-needed:]
        targets = sorted(targets, key=lambda x: x["r"], reverse=True)

    print("[CLICKER] targets chosen:")
    for t in targets:
        print(" id:", t["id"], "r:", t["r"], "pos:", (t["x"], t["y"]), "color:", t.get("color_name"))

    for t in targets:
        cur = shared_state.get("bubbles", [])
        matched = None
        for cb in cur:
            if cb["id"] == t["id"]:
                matched = cb
                break
        if matched is None:
            # fallback nearest by distance
            best = None
            bestd = float("inf")
            for cb in cur:
                d = math.hypot(cb["x"] - t["x"], cb["y"] - t["y"])
                if d < bestd:
                    bestd = d
                    best = cb
            matched = best

        if matched is None:
            print("[CLICKER] couldn't find match; skipping.")
            continue

        try:
            print(f"[CLICKER] clicking at {(matched['x'], matched['y'])}")
            log_event("click_attempt", target_id=matched["id"], x=matched["x"], y=matched["y"])
            pyautogui.moveTo(matched["x"], matched["y"], duration=0.08)
            pyautogui.click()
            time.sleep(CLICK_DELAY)
            log_event("click_done", target_id=matched["id"], x=matched["x"], y=matched["y"])
        except Exception as e:
            print("[CLICKER] click failed:", e)

    print("[CLICKER] finished.")
    log_event("clicker_done", targets=[t["id"] for t in targets])

# -------------------------
# Main runner
# -------------------------
def main():
    print("custom_agent_browser starting.")
    while True:
        coords = find_window_by_title_substr()
        if not coords:
            print("Window with title substring not found. Exiting.")
            break

        shared_state["window_coords"] = coords
        print("Found window:", coords.get("title", ""), coords)

        shared_state["instruction"] = None
        shared_state["bubbles"] = []
        shared_state["running"] = True

        t_track = threading.Thread(target=bubble_tracking_thread, name="TrackThread", daemon=True)
        t_ocr = threading.Thread(target=ocr_read_hud_thread, name="OCRThread", daemon=True)
        t_clicker = threading.Thread(target=choose_targets_and_click, name="ClickerThread", daemon=True)

        t_track.start()
        t_ocr.start()
        t_clicker.start()

        # Wait for OCR+clicker to finish (timeouts are conservative)
        t_ocr.join(timeout=40)
        t_clicker.join(timeout=30)

        shared_state["running"] = False
        t_track.join(timeout=2)

        time.sleep(1)
        print("Round finished. Checking for window again...")

    print("Agent finished. events:")
    for e in shared_state["events"]:
        ts = datetime.fromtimestamp(e["time"]).isoformat()
        print(ts, e["type"], {k: v for k, v in e.items() if k not in ("time","type")})

if __name__ == "__main__":
    main()

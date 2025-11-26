#!/usr/bin/env python3
"""
custom_agent_browser.py

Agent that finds a browser window by title (substring), OCRs the HUD (canvas top),
tracks bubbles in the canvas area, and clicks the correct bubbles.
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
import random

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
WINDOW_TITLE_SUBSTR = "Bubble CAPTCHA"
HUD_HEIGHT = 56
HUD_LEFT_MARGIN = 10
HUD_RIGHT_MARGIN = 10
PLAY_TOP_MARGIN = 12         # distance from HUD bottom to play area (approx)
PLAY_BOTTOM_MARGIN = 40      # footer area size in your game
TRACK_FPS = 20
CLICK_DELAY = 0.12
MAX_OCR_ATTEMPTS = 20

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
}

shared_state = {
    "instruction": None,    # { "text", "no_of_bubbles", "bubble_order" }
    "bubbles": [],          # tracked bubbles (absolute screen coords)
    "events": [],
    "running": True,
    "window_coords": None,
}

# -------------------------
# Logging
# -------------------------
def log_event(event_type, **kwargs):
    shared_state["events"].append({
        "time": time.time(),
        "type": event_type,
        **kwargs
    })

# -------------------------
# Ensure tesseract exists
# -------------------------
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
    raise FileNotFoundError("Tesseract not found on system.")

# -------------------------
# Bézier mouse movement — REPLACED WITH FAST VERSION
# -------------------------
def bezier_move_mouse(start_x, start_y, end_x, end_y, duration_override=None, max_time=0.06):
    """
    Fast human-like movement along a cubic Bézier curve.
      - Uses a small number of steps and issues moveTo() with duration per step
        so the OS performs smooth motion instead of many tiny immediate jumps.
      - duration scales with distance but stays very short for responsiveness.
      - max_time controls the maximum total duration (seconds).
    """
    sx, sy = float(start_x), float(start_y)
    tx, ty = float(end_x), float(end_y)
    dx, dy = tx - sx, ty - sy
    dist = math.hypot(dx, dy)

    # duration: scale with distance but clamp; allow override
    if duration_override is not None:
        duration = max(0.01, float(duration_override))
    else:
        # base scale: shorter divisor -> faster overall. tuned for speed.
        duration = min(max_time, max(0.01, dist / 1300.0))

    # control points produce a small curvature
    cp1 = (sx + dx * 0.28 + random.uniform(-6, 6), sy + dy * 0.28 + random.uniform(-6, 6))
    cp2 = (sx + dx * 0.72 + random.uniform(-6, 6), sy + dy * 0.72 + random.uniform(-6, 6))

    # steps: small number (4-10) for fast moves; ensures each step has a non-zero duration
    steps = max(4, min(10, int(duration * 120)))  # keep it small and bounded

    log_event("bezier_move_start", start=(sx, sy), target=(tx, ty), dist=dist, duration=duration, steps=steps)

    # do moves using pyautogui.moveTo with a short per-step duration so OS handles interpolation
    for i in range(1, steps + 1):
        t = i / steps
        omt = (1 - t)
        # cubic bezier point
        x = (omt**3)*sx + 3*(omt**2)*t*cp1[0] + 3*omt*(t**2)*cp2[0] + (t**3)*tx
        y = (omt**3)*sy + 3*(omt**2)*t*cp1[1] + 3*omt*(t**2)*cp2[1] + (t**3)*ty

        # micro-jitter (rare)
        if random.random() < 0.08 and i not in (steps, 1):
            x += random.gauss(0, 0.9)
            y += random.gauss(0, 0.9)

        # per-step duration ensures smooth OS-level interpolation
        per_step_dur = duration / steps
        try:
            pyautogui.moveTo(int(x), int(y), duration=per_step_dur)
        except Exception:
            # fallback to instantaneous move if moveTo fails
            try:
                pyautogui.moveTo(int(x), int(y))
            except Exception:
                pass

    # final exact move (ensure we end exactly at the target)
    try:
        pyautogui.moveTo(int(tx), int(ty), duration=0)
    except Exception:
        pass

    log_event("bezier_move_end", final=(tx, ty), duration=duration)
# -------------------------
# Window discovery
# -------------------------
def find_window_by_title_substr(substr=WINDOW_TITLE_SUBSTR, min_width=300, min_height=200):
    system = platform.system()
    if system in ("Windows", "Linux") and gw is not None:
        try:
            for w in gw.getAllWindows():
                title = (w.title or "")
                if substr.lower() in title.lower() and w.width >= min_width and w.height >= min_height:
                    return {"x": w.left, "y": w.top, "width": w.width, "height": w.height, "title": title}
        except:
            return None

    elif system == "Darwin" and CGWindowListCopyWindowInfo:
        window_list = CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly, kCGNullWindowID)
        for w in window_list:
            name = w.get("kCGWindowName", "") or ""
            owner = w.get("kCGWindowOwnerName", "") or ""
            bounds = w.get("kCGWindowBounds", {})
            width = int(bounds.get("Width", 0))
            height = int(bounds.get("Height", 0))
            if substr.lower() in name.lower() or substr.lower() in owner.lower():
                if width >= min_width and height >= min_height:
                    return {
                        "x": int(bounds.get("X", 0)),
                        "y": int(bounds.get("Y", 0)),
                        "width": width,
                        "height": height,
                        "title": name or owner
                    }
    return None

# -------------------------
# OCR Thread
# -------------------------
import re
def ocr_read_hud_thread(max_attempts=MAX_OCR_ATTEMPTS):
    ensure_tesseract()
    attempts = 0

    while attempts < max_attempts and shared_state["running"]:
        attempts += 1
        log_event("ocr_attempt", attempt=attempts)

        coords = shared_state["window_coords"] or find_window_by_title_substr()
        if not coords:
            print(f"[OCR] window not found (attempt {attempts})")
            time.sleep(0.8)
            continue

        x, y, w, h = coords["x"], coords["y"], coords["width"], coords["height"]
        title_offset = 0 if platform.system() == "Darwin" else 30
        hud_region = (x + 60, y + title_offset + 110, w - 120, 100)

        try:
            img = pyautogui.screenshot(region=hud_region)
        except:
            time.sleep(0.4)
            continue

        gray = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(gray, cv2.COLOR_BGR2GRAY)
        _, th = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)

        text = pytesseract.image_to_string(th).strip()
        print("[OCR] reads:", text)
        log_event("ocr_text", raw=text)
        
        # --- SUCCESS DETECTION ---
        success_patterns = [
            r"captcha\s+passed",
            r"captcha\s+assed",
            r"you\s+may\s+proceed"
        ]

        if any(re.search(p, text.lower()) for p in success_patterns):
            print("[OCR] CAPTCHA success detected!")
            shared_state["running"] = False
            return

        # Try to find number and ordering word
        number_match = re.search(r"\b(2|3)\b", text)
        order_match = re.search(r"(ascending|descending)", text, re.I)

        if number_match and order_match:
            instr = {
                "text": text,
                "no_of_bubbles": int(number_match.group(1)),
                "bubble_order": order_match.group(1).lower()
            }
            shared_state["instruction"] = instr
            log_event("ocr_success", instruction=instr)
            print("[OCR] Instruction:", instr)
            return

        time.sleep(0.7)

    print("[OCR] failed after attempts.")
    log_event("ocr_failed")

# -------------------------
# Bubble Tracking Thread
# -------------------------
def color_name_from_bgr(bgr_pixel):
    b, g, r = bgr_pixel
    best, bestd = None, float("inf")
    for name, rgb in COLOR_MAP.items():
        dr, dg, db = r - rgb[0], g - rgb[1], b - rgb[2]
        d = dr*dr + dg*dg + db*db
        if d < bestd:
            bestd, best = d, name
    return best

def bubble_tracking_thread():
    last_frame = []
    next_id = 1

    while shared_state["running"] and shared_state["window_coords"] is None:
        coords = find_window_by_title_substr()
        if coords:
            shared_state["window_coords"] = coords
            break
        time.sleep(0.3)

    coords = shared_state["window_coords"]
    if not coords:
        return

    x, y, w, h = coords["x"], coords["y"], coords["width"], coords["height"]
    title_offset = 0 if platform.system() == "Darwin" else 30
    automation_bar_height = 30  # estimated for Selenium/Chrome
    title_offset += automation_bar_height
    play_region = (
        x + 10,
        y + title_offset + HUD_HEIGHT + PLAY_TOP_MARGIN,
        w - 20,
        h - HUD_HEIGHT - PLAY_TOP_MARGIN - PLAY_BOTTOM_MARGIN
    )

    while shared_state["running"]:
        try:
            img = pyautogui.screenshot(region=play_region)
        except:
            time.sleep(0.2)
            continue

        frame = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.medianBlur(gray, 5)

        circles = cv2.HoughCircles(
            gray, cv2.HOUGH_GRADIENT, dp=HOUGH_DP, minDist=HOUGH_MIN_DIST,
            param1=HOUGH_PARAM1, param2=HOUGH_PARAM2,
            minRadius=HOUGH_MIN_RADIUS, maxRadius=HOUGH_MAX_RADIUS
        )

        detected = []
        if circles is not None:
            circles = np.uint16(np.around(circles))
            for c in circles[0, :]:
                cx, cy, r = c
                color = color_name_from_bgr(frame[cy, cx])
                detected.append({"x": cx, "y": cy, "r": r, "color_name": color})

        assigned, new = [], []
        for d in detected:
            best, bestd = None, float("inf")
            for lf in last_frame:
                dx, dy = d["x"] - lf["x"], d["y"] - lf["y"]
                dd = math.hypot(dx, dy)
                if dd < 50 and dd < bestd and not lf.get("used"):
                    best, bestd = lf, dd
            if best:
                d["id"] = best["id"]
                best["used"] = True
                assigned.append(d)
            else:
                d["id"] = next_id
                next_id += 1
                new.append(d)

        current = assigned + new
        abs_positions = [{
            "id": b["id"],
            "x": play_region[0] + b["x"],
            "y": play_region[1] + b["y"],
            "r": b["r"],
            "color_name": b["color_name"]
        } for b in current]

        shared_state["bubbles"] = abs_positions
        last_frame = [{"id": b["id"], "x": b["x"], "y": b["y"]} for b in detected]

        time.sleep(1 / TRACK_FPS)

# -------------------------
# Clicker Thread (Updated with FAST Bézier movement)
# -------------------------
def choose_targets_and_click():
    while shared_state["running"] and shared_state.get("instruction") is None:
        time.sleep(0.1)

    instr = shared_state["instruction"]
    if not instr:
        return

    needed = instr["no_of_bubbles"]
    order = instr["bubble_order"]

    # allow tracker to populate
    time.sleep(0.5)
    bubbles = list(shared_state["bubbles"])

    uniq = {}
    for b in bubbles:
        uniq[b["id"]] = b
    bubbles = list(uniq.values())
    # sort by radius so ascending/descending is stable
    bubbles.sort(key=lambda x: x["r"])

    # choose targets (your existing logic can go here or the ANY-combo logic)
    if order == "ascending":
        targets = bubbles[:needed]
    else:
        targets = sorted(bubbles[-needed:], key=lambda x: x["r"], reverse=True)

    print("[CLICKER] targets chosen:")
    for t in targets:
        print(" id:", t["id"], "r:", t["r"], "pos:", (t["x"], t["y"]), "color:", t.get("color_name"))

    for t in targets:
        cur = list(shared_state["bubbles"])
        match = next((b for b in cur if b["id"] == t["id"]), None)
        if match is None:
            # fallback nearest by distance
            best, bestd = None, float("inf")
            for cb in cur:
                d = math.hypot(cb["x"] - t["x"], cb["y"] - t["y"])
                if d < bestd:
                    bestd = d
                    best = cb
            match = best

        if match is None:
            print("[CLICKER] couldn't find match; skipping.")
            continue

        # pick a random point *inside* the bubble (reduces misses due to edge-detection)
        radius = max(2, match.get("r", 10))
        offset_x = random.uniform(-0.25 * radius, 0.25 * radius)
        offset_y = random.uniform(-0.25 * radius, 0.25 * radius)
        target_x = int(match["x"] + offset_x)
        target_y = int(match["y"] + offset_y)

        try:
            # start from current cursor (fetch once)
            sx, sy = pyautogui.position()

            # very fast bezier move (max_time tuned above)
            bezier_move_mouse(sx, sy, target_x, target_y, duration_override=None, max_time=0.06)

            # tiny pause to let the OS settle (very short)
            time.sleep(random.uniform(0.008, 0.03))

            # final tiny jiggle before click (very small)
            if random.random() < 0.3:
                jig_x = target_x + random.uniform(-0.8, 0.8)
                jig_y = target_y + random.uniform(-0.8, 0.8)
                try:
                    pyautogui.moveTo(int(jig_x), int(jig_y), duration=0)
                except Exception:
                    pass

            pyautogui.click()
            time.sleep(CLICK_DELAY)
            log_event("click_done", target_id=match["id"], x=target_x, y=target_y)
        except Exception as e:
            print("[CLICKER] click failed:", e)

    print("[CLICKER] finished.")
    log_event("clicker_done", targets=[t["id"] for t in targets])
# -------------------------
# Main Runner
# -------------------------
def main():
    print("Agent starting…")

    while True:
        coords = find_window_by_title_substr()
        if not coords:
            print("Window not found. Exiting.")
            break

        shared_state["window_coords"] = coords
        shared_state["instruction"] = None
        shared_state["bubbles"] = []
        shared_state["running"] = True

        t_track = threading.Thread(target=bubble_tracking_thread, daemon=True)
        t_ocr = threading.Thread(target=ocr_read_hud_thread, daemon=True)
        t_click = threading.Thread(target=choose_targets_and_click, daemon=True)

        t_track.start()
        t_ocr.start()
        t_click.start()

        t_ocr.join(timeout=40)
        t_click.join(timeout=30)

        shared_state["running"] = False
        t_track.join(timeout=2)

        if shared_state.get("instruction") is None:
            # OCR detected success, stop restarting
            print("CAPTCHA passed. Agent terminating.")
            break

        time.sleep(1)
        print("Round finished. Restarting...")


    print("Agent terminated. Event log:")
    for e in shared_state["events"]:
        print(datetime.fromtimestamp(e["time"]).isoformat(), e["type"], {k: v for k, v in e.items() if k not in ("time","type")})

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
custom_agent.py
- Run after launching captcha_bubbles_v1.py (the Pygame CAPTCHA).
- Detects the window cross-platform, OCRs HUD instruction, tracks bubbles in real-time,
  then clicks the correct bubbles according to the instruction.

Notes:
- Designed to be explanatory and practical. Read comments to understand flow.
- Tweak timing constants and Hough params if detection misses small/fast bubbles.
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
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
import numpy as np
import cv2

# Try to import pygetwindow (Windows/Linux). On mac, we'll use Quartz.
try:
    import pygetwindow as gw
except Exception:
    gw = None

# macOS Quartz
if platform.system() == "Darwin":
    try:
        from Quartz import CGWindowListCopyWindowInfo, kCGWindowListOptionOnScreenOnly, kCGNullWindowID
    except Exception:
        CGWindowListCopyWindowInfo = None

# --- Configuration (tweak as needed) ---
WINDOW_TITLE = "Anti-AI Bubble CAPTCHA"
HUD_HEIGHT = 80              # pixels to capture from top for OCR HUD
HUD_LEFT_MARGIN = 10
HUD_RIGHT_MARGIN = 10
PLAY_TOP_MARGIN = 12         # distance from HUD bottom to play area
PLAY_BOTTOM_MARGIN = 40      # footer area size in your game
TRACK_FPS = 15               # target capture FPS for tracking
CLICK_DELAY = 0.15           # small delay between automated clicks
MAX_OCR_ATTEMPTS = 15

# COLOR map matches the game COLOR_MAP
COLOR_MAP = {
    "BLUE":   (80, 160, 255),
    "RED":    (230, 80, 80),
    "GREEN":  (80, 200, 120),
    "YELLOW": (240, 220, 80),
    "ORANGE": (245, 170, 80),
}
COLOR_NAMES = list(COLOR_MAP.keys())

# Shared state for threads to communicate
shared_state = {
    "instruction": None,    # {"text", "no_of_bubbles", "bubble_order"}
    "bubbles": [],          # list of tracked bubbles dicts
    "events": [],           # logs: dict entries
    "running": True,
    "window_coords": None,  # detected window coords
}


# -------------------------
# Utility & OS detection
# -------------------------
def log_event(event_type, **kwargs):
    t = time.time()
    shared_state["events"].append({"time": t, "type": event_type, **kwargs})


def ensure_tesseract():
    """Auto-detect tesseract binary and set pytesseract path."""
    # If user already set pytesseract.pytesseract.tesseract_cmd externally,
    # this will use it. Otherwise try to detect.
    if getattr(pytesseract.pytesseract, "tesseract_cmd", None):
        return

    system = platform.system()
    if system == "Windows":
        # common Windows path; allow fallback to PATH lookup
        candidate = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        if shutil.which("tesseract"):
            pytesseract.pytesseract.tesseract_cmd = shutil.which("tesseract")
        elif shutil.os.path.exists(candidate):
            pytesseract.pytesseract.tesseract_cmd = candidate
        else:
            raise FileNotFoundError("Tesseract not found on Windows. Install and/or add to PATH.")
    else:
        # macOS / Linux - rely on PATH
        which = shutil.which("tesseract")
        if which:
            pytesseract.pytesseract.tesseract_cmd = which
        else:
            raise FileNotFoundError("Tesseract not found. On mac: 'brew install tesseract', on Linux: 'sudo apt install tesseract-ocr'.")


# -------------------------
# Cross-platform window detection
# -------------------------
def find_window_mac(min_width=400, min_height=200):
    """macOS heuristic: find first visible python-owned window big enough (works with Pygame)."""
    if CGWindowListCopyWindowInfo is None:
        return None

    window_list = CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly, kCGNullWindowID)
    for w in window_list:
        owner = w.get("kCGWindowOwnerName", "") or ""
        name = w.get("kCGWindowName", "") or ""
        bounds = w.get("kCGWindowBounds", {}) or {}
        width = int(bounds.get("Width", 0))
        height = int(bounds.get("Height", 0))
        # Heuristic: Pygame windows usually belong to Python and match our size
        if owner.lower().startswith("python") and width >= min_width and height >= min_height:
            x = int(bounds.get("X", 0))
            y = int(bounds.get("Y", 0))
            return {"x": x, "y": y, "width": width, "height": height}
    return None


def find_window(title=WINDOW_TITLE):
    """Return dict {x,y,width,height} or None"""
    system = platform.system()
    if system in ("Windows", "Linux") and gw is not None:
        try:
            wins = gw.getWindowsWithTitle(title)
            if not wins:
                return None
            w = wins[0]
            return {"x": w.left, "y": w.top, "width": w.width, "height": w.height}
        except Exception:
            return None
    elif system == "Darwin":
        return find_window_mac()
    else:
        return None


# -------------------------
# OCR thread
# -------------------------
import re
def ocr_read_hud_thread(max_attempts=MAX_OCR_ATTEMPTS):
    """
    Continuously attempts to OCR the HUD until it finds "2 or 3" and "ascending/descending".
    Sets shared_state['instruction'] on success.
    """
    ensure_tesseract()
    attempts = 0
    while attempts < max_attempts and shared_state["running"]:
        attempts += 1
        log_event("ocr_attempt", attempt=attempts)
        coords = shared_state.get("window_coords") or find_window()
        if not coords:
            print(f"[OCR] Window not found (attempt {attempts}/{max_attempts}). Retrying...")
            time.sleep(1)
            continue

        x, y, w, h = coords["x"], coords["y"], coords["width"], coords["height"]
        # On Windows, there is a title bar; on mac we used bounds directly
        title_bar_height = 30 if platform.system() == "Windows" else 0
        hud_region = (
            int(x + HUD_LEFT_MARGIN),
            int(y + 6 + title_bar_height),
            int(w - HUD_LEFT_MARGIN - HUD_RIGHT_MARGIN),
            int(HUD_HEIGHT),
        )

        # Screenshot the HUD region
        try:
            img = pyautogui.screenshot(region=hud_region)
        except Exception as e:
            print("[OCR] screenshot failed:", e)
            time.sleep(0.5)
            continue

        # Convert to grayscale for better OCR
        frame = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        # small threshold to help OCR
        _, th = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)

        text = pytesseract.image_to_string(th).strip()
        print("[OCR] reads:\n", text)
        log_event("ocr_text", raw=text)

        number_match = re.search(r"\b(2|3)\b", text)
        order_match = re.search(r"\b(a?scending|d[e3]scending|desoending)\b", text, re.IGNORECASE)

        if number_match and order_match:
            instruction = {
                "text": text,
                "no_of_bubbles": int(number_match.group(1)),
                "bubble_order": order_match.group(1).lower()
            }
            shared_state["instruction"] = instruction
            print("[OCR] Instruction extracted:", instruction)
            log_event("ocr_success", instruction=instruction)
            return instruction

        print("[OCR] failed to parse instruction. retrying...")
        time.sleep(0.8)

    print("[OCR] giving up after attempts.")
    log_event("ocr_failed", attempts=attempts)
    return None


# -------------------------
# Bubble tracking thread
# -------------------------
# Simple tracker: detect circles via Hough and match color by reading center pixel.
# Also does simple ID assignment using nearest-neighbor to previous frame for continuity.
def color_name_from_bgr(bgr_pixel):
    """Map BGR pixel to nearest color name from COLOR_MAP using Euclidean distance."""
    b, g, r = int(bgr_pixel[0]), int(bgr_pixel[1]), int(bgr_pixel[2])
    best = None
    best_d = float("inf")
    for name, rgb in COLOR_MAP.items():
        # COLOR_MAP stored in (R,G,B) — compare appropriately
        dr = r - rgb[0]
        dg = g - rgb[1]
        db = b - rgb[2]
        d = dr*dr + dg*dg + db*db
        if d < best_d:
            best_d = d
            best = name
    return best

def bubble_tracking_thread():
    last_frame_bubbles = []  # list of dicts with id, x, y, r, color_name
    next_id = 1
    # Wait until window coords are known
    while shared_state["running"] and shared_state.get("window_coords") is None:
        c = find_window()
        if c:
            shared_state["window_coords"] = c
            print("[TRACK] detected window coords:", c)
            break
        time.sleep(0.5)

    coords = shared_state["window_coords"]
    if not coords:
        print("[TRACK] window not found; exiting tracker.")
        return

    # Compute play area inside window (approx per your game layout)
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

        # Hough circle detection - tune param2 (threshold) if misses
        circles = cv2.HoughCircles(gray, cv2.HOUGH_GRADIENT, dp=1.2, minDist=30,
                                   param1=50, param2=28, minRadius=12, maxRadius=70)
        frame_bubbles = []

        if circles is not None:
            circles = np.uint16(np.around(circles))
            for c in circles[0, :]:
                cx, cy, r = int(c[0]), int(c[1]), int(c[2])
                # sample center pixel (with bounds check)
                sx = min(max(cx, 0), frame.shape[1]-1)
                sy = min(max(cy, 0), frame.shape[0]-1)
                bgr = frame[sy, sx].tolist()
                color_name = color_name_from_bgr(bgr)
                frame_bubbles.append({"x": cx, "y": cy, "r": r, "color_name": color_name})

        # Simple nearest-neighbor ID assignment to preserve identity across frames
        assigned = []
        new_bubbles = []
        for fb in frame_bubbles:
            best_match = None
            best_d = float("inf")
            for lb in last_frame_bubbles:
                dx = fb["x"] - lb["x"]
                dy = fb["y"] - lb["y"]
                d = math.hypot(dx, dy)
                if d < 50 and d < best_d and lb.get("assigned") is not True:
                    best_d = d
                    best_match = lb
            if best_match is not None:
                # reuse id
                fb["id"] = best_match["id"]
                best_match["assigned"] = True
                assigned.append(fb)
            else:
                fb["id"] = None
                new_bubbles.append(fb)

        # give ids to new ones
        for nb in new_bubbles:
            nb["id"] = next_id
            next_id += 1

        # Merge assigned + new => current frame
        current_bubbles = assigned + new_bubbles

        # Convert to absolute screen coordinates (for clicking later)
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

        # update last_frame_bubbles (reset assigned flag)
        last_frame_bubbles = [{"id": b["id"], "x": b["x"], "y": b["y"]} for b in frame_bubbles]

        # maintain loop timing
        elapsed = time.time() - t0
        to_sleep = max(0.0, capture_interval - elapsed)
        time.sleep(to_sleep)

    log_event("track_stop")
    print("[TRACK] tracker exiting.")


# -------------------------
# Clicker: choose and click bubbles based on instruction
# -------------------------
def choose_targets_and_click():
    """Wait until instruction available, then pick bubbles as required and click them."""
    # wait for instruction
    while shared_state["running"] and shared_state.get("instruction") is None:
        time.sleep(0.2)

    instr = shared_state.get("instruction")
    if not instr:
        print("[CLICKER] No instruction; exiting.")
        return

    needed = instr["no_of_bubbles"]
    order = instr["bubble_order"]  # "ascending" or "descending"
    print(f"[CLICKER] Instruction received: burst {needed} bubbles in {order} order.")

    # Wait a little to allow tracker to have stable positions
    time.sleep(0.6)

    # copy bubbles snapshot
    b_snapshot = list(shared_state.get("bubbles", []))
    if not b_snapshot:
        print("[CLICKER] No bubbles tracked; aborting.")
        return

    # deduplicate by id (choose highest radius representative)
    uniq = {}
    for b in b_snapshot:
        uniq[b["id"]] = b
    bubble_list = list(uniq.values())

    # Sort by radius
    bubble_list.sort(key=lambda x: x["r"])

    if order == "ascending":
        targets = bubble_list[:needed]
    else:
        targets = bubble_list[-needed:]
        # if descending, they're in ascending order now; reverse to get descending order of size
        targets = sorted(targets, key=lambda x: x["r"], reverse=True)

    print("[CLICKER] Targets chosen (screen coords):")
    for t in targets:
        print("  id:", t["id"], "r:", t["r"], "pos:", (t["x"], t["y"]), "color:", t.get("color_name"))

    # Click each target with small delay
    for t in targets:
        # safety check: ensure still within tracked bubbles (position may have moved)
        cur = shared_state.get("bubbles", [])
        # find nearest current bubble to target id (or nearest by distance)
        matched = None
        for cb in cur:
            if cb["id"] == t["id"]:
                matched = cb
                break
        if matched is None:
            # fallback: nearest by distance
            best = None
            bestd = float("inf")
            for cb in cur:
                d = math.hypot(cb["x"] - t["x"], cb["y"] - t["y"])
                if d < bestd:
                    bestd = d
                    best = cb
            matched = best

        if matched is None:
            print("[CLICKER] couldn't find a match for target; skipping.")
            continue

        # perform click (move and click)
        try:
            print(f"[CLICKER] Clicking at {(matched['x'], matched['y'])}")
            log_event("click_attempt", target_id=matched["id"], x=matched["x"], y=matched["y"])
            pyautogui.moveTo(matched["x"], matched["y"], duration=0.08)
            pyautogui.click()
            time.sleep(CLICK_DELAY)
            log_event("click_done", target_id=matched["id"], x=matched["x"], y=matched["y"])
        except Exception as e:
            print("[CLICKER] click failed:", e)

    print("[CLICKER] finished clicking targets.")
    log_event("clicker_done", targets=[t["id"] for t in targets])


# -------------------------
# Main
# -------------------------
def main():
    print("custom_agent starting.")

    while True:
        # Check if CAPTCHA window exists
        coords = find_window()
        if not coords:
            print("CAPTCHA window not found. Assuming solved or closed. Exiting.")
            break

        shared_state["window_coords"] = coords
        print("Found window coords:", coords)

        # Reset shared state for this round
        shared_state["instruction"] = None
        shared_state["bubbles"] = []
        shared_state["running"] = True

        # Start threads: OCR, tracker, clicker
        t_ocr = threading.Thread(target=ocr_read_hud_thread, name="OCRThread", daemon=True)
        t_track = threading.Thread(target=bubble_tracking_thread, name="TrackThread", daemon=True)
        t_clicker = threading.Thread(target=choose_targets_and_click, name="ClickerThread", daemon=True)

        t_track.start()
        t_ocr.start()
        t_clicker.start()

        # Wait for OCR and clicker to finish for this round
        t_ocr.join(timeout=60)
        t_clicker.join(timeout=30)

        # Stop tracker for this round
        shared_state["running"] = False
        t_track.join(timeout=2)

        # Small delay before next round
        time.sleep(1)
        print("Round finished. Checking if CAPTCHA is still present...")

    print("Agent finished. All rounds completed.")
    for e in shared_state["events"]:
        ts = datetime.fromtimestamp(e["time"]).isoformat()
        print(ts, e["type"], {k: v for k, v in e.items() if k not in ("time", "type")})

if __name__ == "__main__":
    main()
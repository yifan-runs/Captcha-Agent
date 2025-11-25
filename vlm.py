import threading
import queue
import time
from typing import Tuple, List, Dict
import ollama
from tracker import kalman_tracker_worker
import cv2
import random
import json
from selenium_portal import SeleniumPortal

def jitter_tween_factory(jitter_strength: float = 0.05):
    def jitter_tween(t: float) -> float:
        base = t * t * (3 - 2 * t)
        jitter = (random.random() - 0.5) * 2 * jitter_strength
        v = base + jitter
        return max(0.0, min(1.0, v))
    return jitter_tween

jitter_tween = jitter_tween_factory(float(random.randrange(40, 80)) * 0.001)

sp: SeleniumPortal = SeleniumPortal("http://127.0.0.1:5000/captcha")
q: queue.Queue[Tuple] = queue.Queue(maxsize=1)
stop_ev = threading.Event()
tracker_thread = threading.Thread(
    target=kalman_tracker_worker,
    args=(q, stop_ev),
    kwargs={
        "source": sp,
        "roi": (0.0, 0.18, 1.0, 0.95),
        "max_dist": 150,
        "max_misses": 60,
        "put_timeout": 0.01,
        "show_window": True
    },
    daemon=True
)
tracker_thread.start()

client = ollama.Client(host="", timeout=60)
# MODEL_NAME = "moondream:1.8b"
# MODEL_NAME = "qwen3-vl:2b"
MODEL_NAME = "minicpm-v:8b"
# MODEL_NAME = "granite3.2-vision:2b"
print(client.show(MODEL_NAME))
client.chat(
    model=MODEL_NAME,
    messages=[{"role": "user", "content": "You are an agent controlling clicks on moving bubbles.\nWait until your first assignment."}],
    keep_alive=-1,
    stream=False,
)

try:
    while True:
        time.sleep(0.01)
        try:
            frame, roi, readings = q.get(timeout=0.1)
        except queue.Empty:
            continue

        if not readings:
            continue

        prompt_text = "You are an agent controlling clicks on moving bubbles.\n"
        prompt_text += "The current tracked objects are listed as follows:\n"
        prompt_text += "["
        for r in readings:
            prompt_text += f"{{'id':{r['id']},'x':{int(r['cx'])},'y':{int(r['cy'])}}},"
        prompt_text += "]\n"
        prompt_text += (
            "Select the IDs to click according to the rules defined on the screen.\n"
            "Some IDs may point to non-existent bubbles, make sure each selected ID hovers over a real bubble.\n"
            "Approximate the size in pixels of each bubble before making any decisions.\n"
            "Output exactly in order of the rules you have read from the image i.e. {\"click_ids\":[ID1,ID2,...]} where ID1,ID2,... must be integers.\n"
        )

        ok, buffer = cv2.imencode(".jpg", frame)
        if not ok:
            print("Failed to encode frame, skipping this iteration")
            continue
        image_bytes = buffer.tobytes()
        print(prompt_text)
        try:
            response = client.chat(
                model=MODEL_NAME,
                messages=[
                    {
                        "role": "user",
                        "content": prompt_text,
                        "images": [image_bytes],
                    }
                ],
                format="json",
                keep_alive=-1,
                stream=False,
                think=False,
            )

            raw_content = response.message.content
            print("RAW:", raw_content)
            data = json.loads(raw_content)
            click_ids = data.get("click_ids", [])
            if not isinstance(click_ids, list):
                raise ValueError("click_ids is not a list")
            print("click_ids:", click_ids)
        except Exception as e:
            print("LLM call / JSON parse failed:", e)
            click_ids = []

        try: # get new locations
            frame, _, readings = q.get(timeout=1) # longer timeout just in case
        except queue.Empty:
            continue
        
        frame_h, frame_w = frame.shape[:2]
        valid_readings = [
            r for r in readings
            if 0 <= r["cx"] < frame_w and 0 <= r["cy"] < frame_h
        ]
        
        for cid in click_ids:
            obj = next((r for r in valid_readings if r["id"] == cid), None)
            if obj:
                x, y = obj["cx"], obj["cy"]
                sp.moveTo(x, y, duration=(random.randrange(80, 160) * 0.001), tween=jitter_tween)
                sp.mouseDown(duration=(random.randrange(20, 50) * 0.001))
                sp.mouseUp()

finally:
    stop_ev.set()
    tracker_thread.join(timeout=2.0)
### VLM Attacker OBS Virtual Camera Replacement
# to allow for headless browser video capture and control
# Sebastian Damodar Slawski
# 21367338
###

import time, cv2, numpy as np
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
import random

class SeleniumPortal:
    def __init__(self, url, canvas_selector="#captchaCanvas", headless=True):
        o = Options()
        if headless:
            o.add_argument("--headless")
            o.add_argument("--no-sandbox")
            o.add_argument("--disable-dev-shm-usage")
            o.add_argument("--disable-gpu")
        self.driver = webdriver.Chrome(options=o)
        self.driver.set_window_size(800, 600)
        self.driver.get(url)
        self.canvas = self.driver.find_element(By.CSS_SELECTOR, canvas_selector)

        size = self.canvas.size
        self._canvas_w = int(size["width"])
        self._canvas_h = int(size["height"])

        arr = np.frombuffer(self.canvas.screenshot_as_png, np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        fh, fw = frame.shape[:2]
        self._scale_x = fw / self._canvas_w if self._canvas_w else 1.0
        self._scale_y = fh / self._canvas_h if self._canvas_h else 1.0
        self._pos = (self._canvas_w // 2, self._canvas_h // 2)

    def isOpened(self):
        return self.driver is not None

    def read(self):
        if not self.isOpened():
            return False, None
        arr = np.frombuffer(self.canvas.screenshot_as_png, np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        return frame is not None, frame

    def release(self):
        if self.driver:
            self.driver.quit()
            self.driver = None

    def _dispatch_mouse_event(self, event_type: str, mx: float, my: float):
        self.driver.execute_script(
            """
            const canvas = arguments[0];
            const mx = arguments[1];
            const my = arguments[2];
            const type = arguments[3];
            const rect = canvas.getBoundingClientRect();
            const evt = new MouseEvent(type, {
                bubbles: true,
                cancelable: true,
                view: window,
                clientX: rect.left + mx,
                clientY: rect.top + my
            });
            canvas.dispatchEvent(evt);
            """,
            self.canvas,
            float(mx),
            float(my),
            event_type,
        )

    def moveTo(self, screen_x, screen_y, duration=0.1, tween=None):
        if tween is None:
            tween = lambda t: t

        tx = screen_x / self._scale_x
        ty = screen_y / self._scale_y
        tx = max(0, min(self._canvas_w - 1, int(tx)))
        ty = max(0, min(self._canvas_h - 1, int(ty)))

        sx, sy = self._pos
        steps = max(1, int(duration / 0.01))

        for i in range(1, steps + 1):
            t = tween(i / steps)
            mx = sx + (tx - sx) * t
            my = sy + (ty - sy) * t
            if i < steps:
                # Jitter until the last step
                mx += random.randint(-5, 5)
                my += random.randint(-5, 5)
            mx = max(0, min(self._canvas_w - 1, mx))
            my = max(0, min(self._canvas_h - 1, my))
            self._dispatch_mouse_event("mousemove", int(mx), int(my))
            self._pos = (int(mx), int(my))
            time.sleep(duration / steps)

        self._pos = (tx, ty)

    def mouseDown(self, duration=0.03):
        mx, my = self._pos
        self._dispatch_mouse_event("mousedown", mx, my)
        time.sleep(duration)

    def mouseUp(self):
        mx, my = self._pos
        self._dispatch_mouse_event("mouseup", mx, my)
        self._dispatch_mouse_event("click", mx, my)

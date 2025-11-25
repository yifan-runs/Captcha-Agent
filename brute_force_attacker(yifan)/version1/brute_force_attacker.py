import pyautogui
import random
import time
import numpy as np
from typing import List, Tuple


class BruteForceAttacker:
    def __init__(self, screen_width: int = 1920, screen_height: int = 1080):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.grid_size = None
        self.click_delay = 0.1

    def set_grid_size(self, rows: int, cols: int):
        self.grid_rows = rows
        self.grid_cols = cols
        self.grid_size = (rows, cols)

    def generate_grid_points(self) -> List[Tuple[int, int]]:
        if self.grid_size is None:
            self.set_grid_size(5, 5)

        points = []
        cell_width = self.screen_width // self.grid_cols
        cell_height = self.screen_height // self.grid_rows

        for row in range(self.grid_rows):
            for col in range(self.grid_cols):
                x = col * cell_width + cell_width // 2
                y = row * cell_height + cell_height // 2
                points.append((x, y))

        return points

    def sequential_attack(self, points: List[Tuple[int, int]]) -> bool:
        print("Starting sequential clicking attack...")

        for i, (x, y) in enumerate(points):
            print(f"Clicking point {i+1}/{len(points)}: ({x}, {y})")

            try:
                pyautogui.moveTo(x, y, duration=0.1)
                pyautogui.click()
                time.sleep(self.click_delay)

                # Add success-detection logic here
                # For example: if captcha disappears or success message appears, return True

            except pyautogui.FailSafeException:
                print("Fail-safe triggered, stopping attack")
                return False

        return False

    def random_attack(self, points: List[Tuple[int, int]], max_attempts: int = 100) -> bool:
        print("Starting random clicking attack...")

        random_points = points.copy()
        random.shuffle(random_points)

        for i, (x, y) in enumerate(random_points[:max_attempts]):
            print(f"Random click {i+1}/{min(len(points), max_attempts)}: ({x}, {y})")

            try:
                pyautogui.moveTo(x, y, duration=0.1)
                pyautogui.click()
                time.sleep(self.click_delay)

            except pyautogui.FailSafeException:
                print("Fail-safe triggered, stopping attack")
                return False

        return False

    def spiral_attack(self, center_x: int = None, center_y: int = None, radius: int = 500, step: int = 50) -> bool:
        print("Starting spiral clicking attack...")

        if center_x is None:
            center_x = self.screen_width // 2
        if center_y is None:
            center_y = self.screen_height // 2

        angle = 0
        current_radius = 0

        while current_radius <= radius:
            x = center_x + int(current_radius * np.cos(angle))
            y = center_y + int(current_radius * np.sin(angle))

            if 0 <= x < self.screen_width and 0 <= y < self.screen_height:
                print(f"Spiral click at: ({x}, {y})")

                try:
                    pyautogui.moveTo(x, y, duration=0.1)
                    pyautogui.click()
                    time.sleep(self.click_delay)

                except pyautogui.FailSafeException:
                    print("Fail-safe triggered, stopping attack")
                    return False

            angle += 0.1
            if angle >= 2 * np.pi:
                angle = 0
                current_radius += step

        return False

    def run_attack(self, attack_method: str = "sequential", **kwargs) -> bool:
        print(f"Launching brute-force attacker — Method: {attack_method}")
        print(f"Screen resolution: {self.screen_width} x {self.screen_height}")
        print("Starting attack in 5 seconds, please switch to the captcha window...")
        time.sleep(5)

        pyautogui.FAILSAFE = True

        try:
            if attack_method == "sequential":
                if self.grid_size is None:
                    self.set_grid_size(6, 6)
                points = self.generate_grid_points()
                return self.sequential_attack(points)

            elif attack_method == "random":
                if self.grid_size is None:
                    self.set_grid_size(8, 8)
                points = self.generate_grid_points()
                return self.random_attack(points, kwargs.get('max_attempts', 100))

            elif attack_method == "spiral":
                return self.spiral_attack(
                    kwargs.get('center_x'), kwargs.get('center_y'), kwargs.get('radius', 500), kwargs.get('step', 50)
                )

            else:
                print(f"Unknown attack method: {attack_method}")
                return False

        except Exception as e:
            print(f"An error occurred during the attack: {e}")
            return False

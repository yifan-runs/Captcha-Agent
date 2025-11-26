from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
import time
import os
import urllib.parse


class HeadlessBubbleAttacker:
    def __init__(self, headless=True):
        self.chrome_options = Options()

        if headless:
            self.chrome_options.add_argument("--headless=new")
        self.chrome_options.add_argument("--no-sandbox")
        self.chrome_options.add_argument("--disable-dev-shm-usage")
        self.chrome_options.add_argument("--disable-gpu")
        self.chrome_options.add_argument("--window-size=800,600")

        self.driver = None
        self.actions = None

    def setup_driver(self):
        """Initialize Chrome driver"""
        try:
            self.driver = webdriver.Chrome(options=self.chrome_options)
            self.actions = ActionChains(self.driver)
            print("Chrome driver initialized successfully")
            return True
        except Exception as e:
            print(f"Driver initialization failed: {e}")
            return False

    def load_local_captcha(self):
        """Load local CAPTCHA page"""
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))

            # First try page.html, then try web_bubble_captcha.html
            captcha_files = ["page.html", "web_bubble_captcha.html"]
            captcha_file = None

            for file_name in captcha_files:
                file_path = os.path.join(current_dir, file_name)
                if os.path.exists(file_path):
                    captcha_file = file_path
                    print(f"Found CAPTCHA file: {file_name}")
                    break

            if not captcha_file:
                print("Error: No CAPTCHA HTML file found")
                # List all files in current directory
                files = os.listdir(current_dir)
                html_files = [f for f in files if f.endswith(".html")]
                print(f"HTML files in current directory: {html_files}")
                return False

            # Build file URL
            file_url = (
                f"file:///{urllib.parse.quote(captcha_file.replace(os.sep, '/'))}"
            )

            print(f"Loading local file: {file_url}")
            self.driver.get(file_url)

            # Wait for page to load - use more lenient conditions
            time.sleep(2)

            # Check if page contains key elements
            page_source = self.driver.page_source
            if "bubble" in page_source.lower() or "captcha" in page_source.lower():
                print("CAPTCHA page loaded successfully")
                return True
            else:
                print("Warning: Page may not have loaded correctly")
                # Save page source for debugging
                with open("debug_page_source.html", "w", encoding="utf-8") as f:
                    f.write(page_source)
                print("Page source saved to debug_page_source.html")
                return True

        except Exception as e:
            print(f"Page loading failed: {e}")
            return False

    def get_instruction(self):
        """Get CAPTCHA instructions"""
        try:
            # Try multiple selectors to find instructions
            selectors = [
                ".hud-instruction",
                "[class*='instruction']",
                "[class*='hud']",
                "div:contains('burst')",  # May require JavaScript
            ]

            for selector in selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        text = element.text.strip()
                        if text and (
                            "burst" in text.lower() or "click" in text.lower()
                        ):
                            instruction_text = text
                            print(f"CAPTCHA instruction: {instruction_text}")

                            # Parse instruction
                            if "ascending" in instruction_text.lower():
                                direction = "ascending"
                            elif "descending" in instruction_text.lower():
                                direction = "descending"
                            else:
                                direction = "ascending"  # default

                            if (
                                "2 bubbles" in instruction_text
                                or "2 bubble" in instruction_text
                            ):
                                count = 2
                            elif (
                                "3 bubbles" in instruction_text
                                or "3 bubble" in instruction_text
                            ):
                                count = 3
                            else:
                                count = 3  # default

                            return direction, count
                except:
                    continue

            # If not found, use JavaScript to find elements with relevant text
            script = """
            var elements = document.querySelectorAll('div, p, span');
            for (var i = 0; i < elements.length; i++) {
                var text = elements[i].textContent || elements[i].innerText;
                if (text && (text.toLowerCase().includes('burst') || text.toLowerCase().includes('bubble'))) {
                    return text;
                }
            }
            return null;
            """
            instruction_text = self.driver.execute_script(script)
            if instruction_text:
                print(f"Found instruction via JS: {instruction_text}")
                return "ascending", 3  # default values
            else:
                print("Warning: Unable to find instruction, using defaults")
                return "ascending", 3

        except Exception as e:
            print(f"Failed to get instruction: {e}, using defaults")
            return "ascending", 3

    def find_bubbles(self):
        """Find all bubbles and get size information"""
        bubbles = []
        try:
            # Try multiple selectors to find bubbles
            selectors = [
                ".bubble",
                "[class*='bubble']",
                "div[style*='border-radius']",
                "div[style*='radius']",
            ]

            for selector in selectors:
                try:
                    bubble_elements = self.driver.find_elements(
                        By.CSS_SELECTOR, selector
                    )
                    if bubble_elements:
                        print(
                            f"Found {len(bubble_elements)} elements using selector '{selector}'"
                        )
                        break
                except:
                    continue
            else:
                print("No bubble elements found")
                return []

            for i, bubble in enumerate(bubble_elements):
                try:
                    # Check if element is visible
                    if not bubble.is_displayed():
                        continue

                    # Get bubble position and size
                    location = bubble.location
                    size = bubble.size
                    radius = size["width"] // 2

                    # Get text content (bubble number)
                    number = bubble.text
                    if not number:
                        number = str(i + 1)

                    # Check if bubble is still alive (no burst class)
                    classes = bubble.get_attribute("class") or ""
                    if "burst" not in classes:
                        bubbles.append(
                            {
                                "element": bubble,
                                "radius": radius,
                                "number": number,
                                "x": location["x"] + radius,
                                "y": location["y"] + radius,
                            }
                        )

                except Exception as e:
                    print(f"Error processing bubble {i}: {e}")
                    continue

            print(f"Found {len(bubbles)} active bubbles")

            # Sort by radius for debugging
            if bubbles:
                sorted_bubbles = sorted(bubbles, key=lambda x: x["radius"])
                for b in sorted_bubbles:
                    print(f"  Bubble {b['number']}: radius {b['radius']}px")
            else:
                print("No active bubbles found")

            return bubbles
        except Exception as e:
            print(f"Failed to find bubbles: {e}")
            return []

    def solve_captcha(self, direction, count, bubbles):
        """Solve CAPTCHA according to instructions"""
        if len(bubbles) < count:
            print(
                f"Error: Not enough bubbles, need {count}, but only have {len(bubbles)}"
            )
            return False

        # Sort bubbles by size
        if direction == "ascending":
            sorted_bubbles = sorted(bubbles, key=lambda x: x["radius"])
        else:  # descending
            sorted_bubbles = sorted(bubbles, key=lambda x: x["radius"], reverse=True)

        # Select first 'count' bubbles
        bubbles_to_click = sorted_bubbles[:count]

        print(f"Need to click {count} bubbles, order: {direction}")
        print("Click plan:")
        for i, bubble in enumerate(bubbles_to_click):
            print(f"  {i+1}. Bubble {bubble['number']} (radius: {bubble['radius']}px)")

        # Click bubbles in order
        for i, bubble in enumerate(bubbles_to_click):
            try:
                print(f"Clicking bubble {i+1} (radius: {bubble['radius']}px)")

                # Scroll element into view
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});",
                    bubble["element"],
                )
                time.sleep(0.5)

                # Use ActionChains for precise clicking
                self.actions.move_to_element(bubble["element"]).click().perform()

                # Wait for animation to complete
                time.sleep(1)

                # Check if failed
                try:
                    result = self.driver.find_element(
                        By.TAG_NAME, "body"
                    ).get_attribute("data-captcha-result")
                    if result == "failed":
                        print("Verification failed! Wrong order")
                        return False
                except:
                    pass  # If no result attribute, continue

            except Exception as e:
                print(f"Failed to click bubble: {e}")
                return False

        return True

    def wait_for_result(self, timeout=10):
        """Wait for verification result"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                # Try multiple ways to check result
                result = self.driver.find_element(By.TAG_NAME, "body").get_attribute(
                    "data-captcha-result"
                )
                if result == "success":
                    print("Verification successful!")
                    return True
                elif result == "failed":
                    print("Verification failed")
                    return False
            except:
                pass

            # Check result banner
            try:
                result_banners = self.driver.find_elements(
                    By.CSS_SELECTOR, "[class*='result'], [class*='banner']"
                )
                for banner in result_banners:
                    text = banner.text.lower()
                    if "success" in text or "passed" in text:
                        print("Verification successful!")
                        return True
                    elif "fail" in text or "error" in text:
                        print("Verification failed")
                        return False
            except:
                pass

            time.sleep(0.5)

        print("Result wait timeout")
        return False

    def run_attack(self):
        """Run attack"""
        print("=== Headless Chrome Bubble CAPTCHA Attack ===")

        if not self.setup_driver():
            return False

        if not self.load_local_captcha():
            return False

        # Save initial screenshot
        self.driver.save_screenshot("initial_page.png")
        print("Initial page screenshot saved")

        # Wait for page to stabilize
        time.sleep(2)

        # Get instructions
        direction, count = self.get_instruction()

        # Multiple attempts (because bubbles are moving)
        max_attempts = 3
        for attempt in range(max_attempts):
            print(f"\n--- Attempt {attempt + 1}/{max_attempts} ---")

            # Find bubbles
            bubbles = self.find_bubbles()
            if len(bubbles) < count:
                print(f"Not enough bubbles, need {count}, found {len(bubbles)}")
                time.sleep(1)
                continue

            # Solve CAPTCHA
            if self.solve_captcha(direction, count, bubbles):
                # Wait for result
                success = self.wait_for_result()
                if success:
                    self.driver.save_screenshot("success_result.png")
                    self.cleanup()
                    return True
            else:
                print("Error during CAPTCHA solving")

            time.sleep(1)

        print("All attempts failed")
        self.driver.save_screenshot("failure_result.png")
        self.cleanup()
        return False

    def cleanup(self):
        """Clean up resources"""
        if self.driver:
            self.driver.quit()
            print("Browser closed")


if __name__ == "__main__":
    # Use Headless mode
    attacker = HeadlessBubbleAttacker(headless=True)

    success = attacker.run_attack()

    if success:
        print("Attack completed successfully!")
    else:
        print("Attack failed")

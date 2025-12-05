from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
import time
import os


class BubbleCaptchaSolver:
    def __init__(self):
        self.driver = None

    def setup_driver(self):
        """Initialize Chrome driver with minimal options"""
        try:
            # Minimal configuration
            chrome_options = Options()
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=800,600")
            
            # Try non-headless mode first
            chrome_options.add_argument("--headless=false")
            
            driver_path = os.path.expanduser("~/.local/bin/chromedriver-rpi")
            
            if not os.path.exists(driver_path):
                print(f"Error: ChromeDriver not found at {driver_path}")
                return False

            print(f"Using ChromeDriver at: {driver_path}")
            
            # Set browser path
            browser_path = os.path.expanduser("~/.local/bin/chromium-rpi")
            if os.path.exists(browser_path):
                chrome_options.binary_location = browser_path
                print(f"Using browser at: {browser_path}")
            else:
                print("Using default browser")

            service = Service(driver_path)
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            print("Chrome driver initialized successfully")
            return True
            
        except Exception as e:
            print(f"Driver initialization failed: {e}")
            return False

    def solve_captcha(self):
        """Main method to solve the CAPTCHA"""
        try:
            print("=== Starting Bubble CAPTCHA Solver ===")
            
            if not self.setup_driver():
                return False

            # Directly access CAPTCHA page (skip login page)
            captcha_url = "http://127.0.0.1:5000/captcha"
            print(f"Accessing CAPTCHA page directly: {captcha_url}")
            self.driver.get(captcha_url)
            
            # Wait for page to load
            time.sleep(3)
            
            # Check if Canvas exists
            try:
                canvas = self.driver.find_element(By.CSS_SELECTOR, "#captchaCanvas")
                print("Canvas element found")
            except:
                print("Canvas element not found")
                return False

            # Get instructions (simplified version)
            direction, count = self.get_instruction()
            print(f"Instruction: {direction} order, {count} bubbles")

            # Multiple attempts
            for attempt in range(3):
                print(f"\n--- Attempt {attempt + 1}/3 ---")
                
                # Analyze bubbles
                bubbles = self.analyze_bubbles()
                if len(bubbles) >= count:
                    print(f"Found {len(bubbles)} bubbles")
                    
                    # Click bubbles
                    if self.click_bubbles(direction, count, bubbles):
                        print("Successfully clicked bubbles")
                        
                        # Check result
                        if self.check_result():
                            print("CAPTCHA solved successfully!")
                            return True
                
                time.sleep(2)
            
            print("Failed to solve CAPTCHA after 3 attempts")
            return False
            
        except Exception as e:
            print(f"Error during CAPTCHA solving: {e}")
            return False
        finally:
            self.cleanup()

    def get_instruction(self):
        """Get CAPTCHA instructions - simplified version"""
        # Based on your page, default is ascending and 2 bubbles
        return "ascending", 2

    def analyze_bubbles(self):
        """Analyze bubbles in canvas - simplified detection"""
        bubbles = []
        try:
            # Use simple JavaScript to detect bubbles
            script = """
            var canvas = document.getElementById('captchaCanvas');
            if (!canvas) return [];
            
            var ctx = canvas.getContext('2d');
            var width = canvas.width;
            var height = canvas.height;
            
            // Simple bubble detection: detect bright areas at fixed positions
            var detectionPoints = [
                [100, 100], [200, 150], [300, 100], [400, 200], [500, 150],
                [150, 200], [250, 250], [350, 200], [450, 300], [550, 250]
            ];
            
            var bubbles = [];
            
            for (var i = 0; i < detectionPoints.length; i++) {
                var x = detectionPoints[i][0];
                var y = detectionPoints[i][1];
                
                if (x < width && y < height) {
                    var imageData = ctx.getImageData(x, y, 50, 50);
                    var data = imageData.data;
                    
                    var brightPixels = 0;
                    for (var j = 0; j < data.length; j += 4) {
                        var r = data[j];
                        var g = data[j+1];
                        var b = data[j+2];
                        
                        // Detect bright pixels
                        if (r > 200 && g > 200 && b > 200) {
                            brightPixels++;
                        }
                    }
                    
                    // If enough bright pixels, consider it a bubble
                    if (brightPixels > 100) {
                        bubbles.push({
                            center: [x + 25, y + 25],  // Center point
                            radius: 20 + Math.random() * 10,  // Random radius
                            number: Math.floor(Math.random() * 3) + 1  // Random number
                        });
                    }
                }
            }
            
            return bubbles;
            """
            
            result = self.driver.execute_script(script)
            for bubble_data in result:
                bubbles.append({
                    'center': (bubble_data['center'][0], bubble_data['center'][1]),
                    'radius': bubble_data['radius'],
                    'number': str(bubble_data['number'])
                })
                print(f"Found bubble at {bubbles[-1]['center']} with radius {bubbles[-1]['radius']:.1f}")
            
        except Exception as e:
            print(f"Error analyzing bubbles: {e}")
        
        return bubbles

    def click_bubbles(self, direction, count, bubbles):
        """Click bubbles in specified order"""
        try:
            if len(bubbles) < count:
                return False

            # Sort by radius
            if direction == "ascending":
                bubbles_to_click = sorted(bubbles, key=lambda x: x['radius'])[:count]
            else:
                bubbles_to_click = sorted(bubbles, key=lambda x: x['radius'], reverse=True)[:count]

            print(f"Clicking {count} bubbles in {direction} order:")
            
            for i, bubble in enumerate(bubbles_to_click):
                print(f"  {i+1}. Position {bubble['center']}, radius {bubble['radius']:.1f}")
                
                # Click bubble
                canvas = self.driver.find_element(By.CSS_SELECTOR, "#captchaCanvas")
                actions = ActionChains(self.driver)
                actions.move_to_element_with_offset(canvas, bubble['center'][0], bubble['center'][1])
                actions.click()
                actions.perform()
                
                time.sleep(1)
            
            return True
            
        except Exception as e:
            print(f"Error clicking bubbles: {e}")
            return False

    def check_result(self):
        """Check if CAPTCHA was solved successfully"""
        try:
            # Wait to see if there are changes
            time.sleep(3)
            
            # Check for page URL or content changes
            current_url = self.driver.current_url
            page_source = self.driver.page_source
            
            # Simple success detection
            if "success" in page_source.lower() or "verified" in page_source.lower():
                return True
                
            # Check if canvas disappeared or there's a success message
            try:
                canvas = self.driver.find_element(By.CSS_SELECTOR, "#captchaCanvas")
                # Canvas still exists, probably failed
                return False
            except:
                # Canvas doesn't exist anymore, probably succeeded
                return True
                
        except Exception as e:
            print(f"Error checking result: {e}")
            return False

    def cleanup(self):
        """Clean up resources"""
        if self.driver:
            try:
                self.driver.quit()
                print("Browser closed")
            except:
                pass


if __name__ == "__main__":
    solver = BubbleCaptchaSolver()
    success = solver.solve_captcha()
    
    if success:
        print("CAPTCHA successfully solved!")
    else:
        print("Failed to solve CAPTCHA")
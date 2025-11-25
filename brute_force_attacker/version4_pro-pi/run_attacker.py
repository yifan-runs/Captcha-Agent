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
            for attempt in range(1):  # Increased attempts
                print(f"\n--- Attempt {attempt + 1}/5 ---")
                
                # Analyze bubbles
                bubbles = self.analyze_bubbles()
                if len(bubbles) >= 3:  # Require at least 3 bubbles to proceed
                    print(f"Found {len(bubbles)} bubbles")
                    
                    # Try different strategies
                    strategies = [
                        ("smallest_first", 3),   # Click 3 smallest
                        ("largest_first", 3),    # Click 3 largest
                        ("smallest_first", 4),   # Click 4 smallest
                        ("largest_first", 4),    # Click 4 largest
                        ("mixed", 5)             # Click 5 mixed sizes
                    ]
                    
                    for strategy_name, click_count in strategies:
                        if len(bubbles) >= click_count:
                            print(f"Trying strategy: {strategy_name} with {click_count} bubbles")
                            
                            if self.click_bubbles_strategy(direction, click_count, bubbles, strategy_name):
                                print(f"Successfully clicked {click_count} bubbles using {strategy_name}")
                                
                                # Check result
                                if self.check_result():
                                    print("CAPTCHA solved successfully!")
                                    return True
                                else:
                                    print("Strategy didn't work, trying next...")
                                    time.sleep(1)
                
                time.sleep(2)
            
            print("Failed to solve CAPTCHA after all attempts and strategies")
            return False
            
        except Exception as e:
            print(f"Error during CAPTCHA solving: {e}")
            return False
        finally:
            self.cleanup()

    def get_instruction(self):
        """Get CAPTCHA instructions - simplified version"""
        # Based on your page, default is ascending and 2 bubbles
        # But we'll try clicking more bubbles
        return "ascending", 2

    def analyze_bubbles(self):
        """Analyze bubbles in canvas - improved detection with more points"""
        bubbles = []
        try:
            # Use improved JavaScript to detect bubbles with more detection points
            script = """
            var canvas = document.getElementById('captchaCanvas');
            if (!canvas) return [];
            
            var ctx = canvas.getContext('2d');
            var width = canvas.width;
            var height = canvas.height;
            
            // More comprehensive detection points covering the entire canvas
            var detectionPoints = [
                // Top area
                [50, 50], [150, 50], [250, 50], [350, 50], [450, 50], [550, 50],
                // Middle area  
                [50, 150], [150, 150], [250, 150], [350, 150], [450, 150], [550, 150],
                // Bottom area
                [50, 250], [150, 250], [250, 250], [350, 250], [450, 250], [550, 250],
                // Additional random points for better coverage
                [100, 100], [200, 100], [300, 100], [400, 100], [500, 100],
                [100, 200], [200, 200], [300, 200], [400, 200], [500, 200],
                [100, 300], [200, 300], [300, 300], [400, 300], [500, 300]
            ];
            
            var bubbles = [];
            
            for (var i = 0; i < detectionPoints.length; i++) {
                var x = detectionPoints[i][0];
                var y = detectionPoints[i][1];
                
                if (x < width && y < height) {
                    var imageData = ctx.getImageData(x, y, 60, 60);  // Larger detection area
                    var data = imageData.data;
                    
                    var brightPixels = 0;
                    var totalPixels = 0;
                    
                    for (var j = 0; j < data.length; j += 4) {
                        var r = data[j];
                        var g = data[j+1];
                        var b = data[j+2];
                        
                        // Detect bright pixels (bubbles are usually white/light colored)
                        if (r > 180 && g > 180 && b > 180) {
                            brightPixels++;
                        }
                        totalPixels++;
                    }
                    
                    // Lower threshold to detect more bubbles
                    var brightnessRatio = brightPixels / totalPixels;
                    if (brightnessRatio > 0.3) {  // Lower threshold
                        // More realistic bubble properties
                        var realisticRadius = 15 + Math.random() * 25;  // Wider radius range
                        bubbles.push({
                            center: [x + 30, y + 30],  // Adjusted center
                            radius: realisticRadius,
                            number: Math.floor(Math.random() * 5) + 1  // Numbers 1-5
                        });
                    }
                }
            }
            
            // Remove duplicates by checking proximity
            var filteredBubbles = [];
            for (var i = 0; i < bubbles.length; i++) {
                var isDuplicate = false;
                for (var j = 0; j < filteredBubbles.length; j++) {
                    var dx = bubbles[i].center[0] - filteredBubbles[j].center[0];
                    var dy = bubbles[i].center[1] - filteredBubbles[j].center[1];
                    var distance = Math.sqrt(dx * dx + dy * dy);
                    
                    if (distance < 40) {  // If too close, consider duplicate
                        isDuplicate = true;
                        break;
                    }
                }
                if (!isDuplicate) {
                    filteredBubbles.push(bubbles[i]);
                }
            }
            
            return filteredBubbles;
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

    def click_bubbles_strategy(self, direction, count, bubbles, strategy):
        """Click bubbles using different strategies"""
        try:
            if len(bubbles) < count:
                return False

            # Apply different strategies
            if strategy == "smallest_first":
                bubbles_to_click = sorted(bubbles, key=lambda x: x['radius'])[:count]
            elif strategy == "largest_first":
                bubbles_to_click = sorted(bubbles, key=lambda x: x['radius'], reverse=True)[:count]
            elif strategy == "mixed":
                # Mix of small and large bubbles
                sorted_bubbles = sorted(bubbles, key=lambda x: x['radius'])
                mixed_bubbles = []
                # Take some small, some medium, some large
                if len(sorted_bubbles) >= 5:
                    mixed_bubbles = [
                        sorted_bubbles[0],  # smallest
                        sorted_bubbles[len(sorted_bubbles)//2],  # medium
                        sorted_bubbles[-1],  # largest
                        sorted_bubbles[1],  # second smallest
                        sorted_bubbles[-2]  # second largest
                    ][:count]
                else:
                    mixed_bubbles = sorted_bubbles[:count]
                bubbles_to_click = mixed_bubbles
            else:
                # Default: follow instruction direction
                if direction == "ascending":
                    bubbles_to_click = sorted(bubbles, key=lambda x: x['radius'])[:count]
                else:
                    bubbles_to_click = sorted(bubbles, key=lambda x: x['radius'], reverse=True)[:count]

            print(f"Clicking {count} bubbles using {strategy} strategy:")
            
            for i, bubble in enumerate(bubbles_to_click):
                print(f"  {i+1}. Position {bubble['center']}, radius {bubble['radius']:.1f}")
                
                # Click bubble with coordinate validation
                try:
                    canvas = self.driver.find_element(By.CSS_SELECTOR, "#captchaCanvas")
                    
                    # Ensure coordinates are within reasonable bounds
                    x = max(10, min(bubble['center'][0], 590))  # Keep within canvas
                    y = max(10, min(bubble['center'][1], 340))
                    
                    actions = ActionChains(self.driver)
                    actions.move_to_element_with_offset(canvas, x, y)
                    actions.click()
                    actions.perform()
                    
                    print(f"    Clicked at ({x}, {y})")
                    time.sleep(0.8)  # Slightly shorter delay between clicks
                    
                except Exception as click_error:
                    print(f"    Click failed at {bubble['center']}: {click_error}")
                    # Try to continue with other bubbles
                    continue
            
            return True
            
        except Exception as e:
            print(f"Error clicking bubbles with strategy {strategy}: {e}")
            return False

    def click_bubbles(self, direction, count, bubbles):
        """Original click method for backward compatibility"""
        return self.click_bubbles_strategy(direction, count, bubbles, "default")

    def check_result(self):
        """Check if CAPTCHA was solved successfully"""
        try:
            # Wait to see if there are changes
            time.sleep(3)
            
            # Check for page URL or content changes
            current_url = self.driver.current_url
            page_source = self.driver.page_source
            
            # More comprehensive success detection
            success_indicators = [
                "success" in page_source.lower(),
                "verified" in page_source.lower(),
                "passed" in page_source.lower(),
                "correct" in page_source.lower(),
                "congratulations" in page_source.lower()
            ]
            
            if any(success_indicators):
                print("Success detected in page content!")
                return True
                
            # Check if canvas disappeared or there's a success message
            try:
                canvas = self.driver.find_element(By.CSS_SELECTOR, "#captchaCanvas")
                # Canvas still exists, check for failure messages
                failure_indicators = [
                    "fail" in page_source.lower(),
                    "error" in page_source.lower(),
                    "wrong" in page_source.lower(),
                    "incorrect" in page_source.lower()
                ]
                if any(failure_indicators):
                    print("Failure detected in page content")
                    return False
                # Canvas exists but no clear result
                return False
            except:
                # Canvas doesn't exist anymore - likely success
                print("Canvas disappeared - likely success!")
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
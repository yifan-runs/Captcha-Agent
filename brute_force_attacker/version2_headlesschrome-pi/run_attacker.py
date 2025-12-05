from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
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
        self.chrome_options.add_argument("--window-size=1200,800")
        
        # 树莓派优化
        self.chrome_options.add_argument("--disable-software-rasterizer")
        self.chrome_options.add_argument("--disable-extensions")

        self.driver = None
        self.actions = None
        self.wait = None

    def setup_driver(self):
        """Initialize Chrome driver using your specific ChromeDriver path"""
        try:
            # 使用您现有的ChromeDriver路径
            driver_path = os.path.expanduser("~/.local/bin/chromedriver-rpi")
            
            if not os.path.exists(driver_path):
                print(f"Error: ChromeDriver not found at {driver_path}")
                print("Please check if ChromeDriver is installed correctly")
                return False

            print(f"Using ChromeDriver at: {driver_path}")
            
            # 尝试找到浏览器可执行文件
            possible_browser_paths = [
                os.path.expanduser("~/.local/bin/chromium-rpi"),
                "/usr/bin/chromium-browser",
                "/usr/bin/google-chrome",
                "/snap/bin/chromium",
            ]
            
            browser_path = None
            for path in possible_browser_paths:
                if os.path.exists(path):
                    browser_path = path
                    self.chrome_options.binary_location = path
                    print(f"Using browser at: {path}")
                    break
            
            if not browser_path:
                print("Warning: Using system default browser")

            # 创建Service并启动driver
            service = Service(driver_path)
            self.driver = webdriver.Chrome(service=service, options=self.chrome_options)
            self.actions = ActionChains(self.driver)
            self.wait = WebDriverWait(self.driver, 15)  # 增加等待时间
            
            print("Chrome driver initialized successfully")
            return True
            
        except Exception as e:
            print(f"Driver initialization failed: {e}")
            # 提供更多调试信息
            print("Please make sure:")
            print("1. ChromeDriver is executable: chmod +x ~/.local/bin/chromedriver-rpi")
            print("2. Chrome/Chromium browser is installed")
            print("3. The user has permission to run ChromeDriver")
            return False

    def load_local_captcha(self):
        """Load local CAPTCHA page"""
        try:
            captcha_path = "/users/pgrad/liy51/yifan/pro_2/page.html"
            
            if not os.path.exists(captcha_path):
                print(f"Error: CAPTCHA file not found at {captcha_path}")
                # 列出目录内容以帮助调试
                dir_path = os.path.dirname(captcha_path)
                if os.path.exists(dir_path):
                    files = os.listdir(dir_path)
                    print(f"Files in directory: {files}")
                return False

            file_url = f"file://{captcha_path}"
            print(f"Loading CAPTCHA from: {file_url}")
            
            self.driver.get(file_url)
            
            # 等待页面加载
            time.sleep(3)
            
            # 检查页面是否包含关键元素
            page_source = self.driver.page_source
            if "bubble" in page_source.lower() or "captcha" in page_source.lower():
                print("CAPTCHA page loaded successfully")
                return True
            else:
                print("Warning: Page loaded but may not contain CAPTCHA elements")
                # 保存页面源代码用于调试
                with open("debug_page.html", "w", encoding="utf-8") as f:
                    f.write(page_source)
                print("Page source saved to debug_page.html")
                return True
            
        except Exception as e:
            print(f"Failed to load CAPTCHA page: {e}")
            return False

    def get_instruction(self):
        """Get CAPTCHA instructions"""
        try:
            # 等待指令元素加载
            time.sleep(2)
            
            instruction_selectors = [
                ".instruction-text",
                ".hud-instruction",
                "[class*='instruction']",
                ".prompt",
                "[class*='prompt']",
            ]
            
            for selector in instruction_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements:
                        if element.is_displayed():
                            text = element.text.strip()
                            if text and len(text) > 5:
                                print(f"Found instruction: {text}")
                                return self._parse_instruction(text)
                except:
                    continue

            # 如果没找到，尝试通过JavaScript搜索
            script = """
            var elements = document.querySelectorAll('*');
            for (var i = 0; i < elements.length; i++) {
                var text = elements[i].textContent || elements[i].innerText;
                if (text && (text.includes('burst') || text.includes('Burst') || 
                             text.includes('bubble') || text.includes('Bubble'))) {
                    return text.trim();
                }
            }
            return null;
            """
            instruction = self.driver.execute_script(script)
            if instruction:
                print(f"Found instruction via JS: {instruction}")
                return self._parse_instruction(instruction)

            print("Using default instructions (ascending, 3 bubbles)")
            return "ascending", 3
            
        except Exception as e:
            print(f"Failed to get instruction: {e}")
            return "ascending", 3

    def _parse_instruction(self, text):
        """Parse instruction text"""
        text_lower = text.lower()
        
        # 确定方向
        if "descending" in text_lower:
            direction = "descending"
        else:
            direction = "ascending"  # 默认
            
        # 确定数量
        count = 3  # 默认
        for i in range(2, 6):
            if f"{i}" in text and ("bubble" in text_lower or "burst" in text_lower):
                count = i
                break
                
        print(f"Parsed instruction: {direction} order, {count} bubbles")
        return direction, count

    def find_bubbles(self):
        """Find all bubbles"""
        bubbles = []
        try:
            # 等待气泡加载
            time.sleep(1)
            
            bubble_selectors = [
                ".bubble",
                "[class*='bubble']",
                "div[style*='border-radius: 50%']",
                "div[style*='border-radius']",
                ".circle",
                "[class*='circle']",
            ]
            
            all_elements = []
            for selector in bubble_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    all_elements.extend(elements)
                except:
                    continue

            print(f"Found {len(all_elements)} potential bubble elements")
            
            for i, element in enumerate(all_elements):
                try:
                    if not element.is_displayed():
                        continue
                        
                    location = element.location
                    size = element.size
                    
                    # 过滤掉太小的元素
                    if size['width'] < 10 or size['height'] < 10:
                        continue
                        
                    radius = min(size['width'], size['height']) // 2
                    
                    # 获取数字
                    number = element.text.strip()
                    if not number:
                        number = str(i + 1)
                    
                    bubbles.append({
                        'element': element,
                        'radius': radius,
                        'number': number,
                        'x': location['x'] + radius,
                        'y': location['y'] + radius,
                    })
                    
                except Exception as e:
                    continue

            print(f"Found {len(bubbles)} valid bubbles")
            
            # 打印气泡信息用于调试
            if bubbles:
                sorted_bubbles = sorted(bubbles, key=lambda x: x['radius'])
                print("Bubbles (sorted by radius):")
                for bubble in sorted_bubbles:
                    print(f"  Number {bubble['number']}: radius {bubble['radius']}px")
            
            return bubbles
            
        except Exception as e:
            print(f"Error finding bubbles: {e}")
            return []

    def solve_captcha(self, direction, count, bubbles):
        """Solve CAPTCHA"""
        if len(bubbles) < count:
            print(f"Not enough bubbles. Need {count}, found {len(bubbles)}")
            return False

        # 按半径排序
        if direction == "ascending":
            sorted_bubbles = sorted(bubbles, key=lambda x: x['radius'])
        else:
            sorted_bubbles = sorted(bubbles, key=lambda x: x['radius'], reverse=True)

        bubbles_to_click = sorted_bubbles[:count]

        print(f"Clicking plan ({direction} order):")
        for i, bubble in enumerate(bubbles_to_click):
            print(f"  {i+1}. Bubble #{bubble['number']} (radius: {bubble['radius']}px)")

        # 点击气泡
        for i, bubble in enumerate(bubbles_to_click):
            try:
                print(f"Clicking bubble {i+1}/#{bubble['number']}...")
                
                # 使用JavaScript点击
                self.driver.execute_script("arguments[0].click();", bubble['element'])
                time.sleep(1.5)  # 等待动画完成
                
            except Exception as e:
                print(f"Failed to click bubble {i+1}: {e}")
                return False

        return True

    def wait_for_result(self, timeout=15):
        """Wait for verification result"""
        print("Waiting for verification result...")
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                # 检查结果属性
                body = self.driver.find_element(By.TAG_NAME, 'body')
                result = body.get_attribute('data-captcha-result')
                if result == 'success':
                    print("CAPTCHA verification successful!")
                    return True
                elif result == 'failed':
                    print("CAPTCHA verification failed!")
                    return False
                    
                # 检查是否有成功/失败消息显示
                success_elements = self.driver.find_elements(By.CSS_SELECTOR, "[class*='success'], [class*='passed']")
                for element in success_elements:
                    if element.is_displayed():
                        print("CAPTCHA verification successful!")
                        return True
                        
                failure_elements = self.driver.find_elements(By.CSS_SELECTOR, "[class*='fail'], [class*='error']")
                for element in failure_elements:
                    if element.is_displayed():
                        print("CAPTCHA verification failed!")
                        return False
                        
            except Exception as e:
                # 忽略检查过程中的错误
                pass
                
            time.sleep(0.5)
            
        print("⏰ Timeout waiting for result")
        return False

    def take_screenshot(self, filename):
        """Take screenshot"""
        try:
            self.driver.save_screenshot(filename)
            print(f"Screenshot saved: {filename}")
        except Exception as e:
            print(f"Failed to take screenshot: {e}")

    def run_attack(self):
        """Run the CAPTCHA attack"""
        print("=== Starting Headless Bubble CAPTCHA Attack ===")
        
        if not self.setup_driver():
            return False
            
        try:
            if not self.load_local_captcha():
                return False
                
            self.take_screenshot("01_initial.png")
            
            # 获取指令
            direction, count = self.get_instruction()
            
            # 多次尝试
            max_attempts = 3
            for attempt in range(max_attempts):
                print(f"\n--- Attempt {attempt + 1}/{max_attempts} ---")
                
                # 查找气泡
                bubbles = self.find_bubbles()
                if len(bubbles) < count:
                    print(f"Not enough bubbles, waiting...")
                    time.sleep(2)
                    continue
                    
                # 解决CAPTCHA
                if self.solve_captcha(direction, count, bubbles):
                    self.take_screenshot(f"02_after_click_{attempt+1}.png")
                    
                    # 等待结果
                    if self.wait_for_result():
                        self.take_screenshot("03_success.png")
                        print("🎊 Attack completed successfully!")
                        return True
                else:
                    print("CAPTCHA solving failed in this attempt")
                    
                time.sleep(2)
                
            print("All attempts failed")
            self.take_screenshot("04_failure.png")
            return False
            
        finally:
            self.cleanup()

    def cleanup(self):
        """Clean up resources"""
        if self.driver:
            self.driver.quit()
            print("Browser closed")


if __name__ == "__main__":
    # 运行攻击
    attacker = HeadlessBubbleAttacker(headless=True)
    success = attacker.run_attack()
    
    if success:
        print("CAPTCHA successfully solved!")
    else:
        print("Failed to solve CAPTCHA")
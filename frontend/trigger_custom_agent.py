"""
Opens a Chrome browser to a login page, fills in credentials, clicks login to trigger
a CAPTCHA popup, and starts a custom agent script to solve the CAPTCHA.

Contributors: Shreya and Amar
"""
import subprocess
import random
import sys
import string
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options

def random_string(n=8):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=n))

# Launch Chrome + Login Page
def launch_login_page(url=" http://127.0.0.1:8080"):
    chrome_options = Options()
    chrome_options.add_experimental_option("detach", True)

    driver = webdriver.Chrome(options=chrome_options)
    driver.get(url)
    return driver

# Fill username & password
def fill_credentials(driver):
    user = "User123"
    password = "Password123!"

    driver.find_element(By.ID, "username").send_keys(user)
    driver.find_element(By.ID, "password").send_keys(password)

    print(f"[+] Entered username={user}, pwd={password}")

# Click the Login button 
# (opens the CAPTCHA popup)
def click_login(driver):
    driver.find_element(By.TAG_NAME, "button").click()
    print("[+] Login clicked - CAPTCHA window should open")

    # delay for popup
    time.sleep(1.5)

# Start captcha-solving agent
def start_agent():
    python_exe = sys.executable
    agent_script = r"C:\Users\shrey\Desktop\Ireland\Trinity\academics\scalable computing\mainproject2\scalable_project2\frontend\custom_agent_browser.py"

    print("[+] Starting custom agent...")
    p = subprocess.Popen([python_exe, agent_script])
    print("[+] Agent started with PID:", p.pid)
    return p

# MAIN WORKFLOW
def main():
    print("[=== START AUTOMATION ===]")

    driver = launch_login_page()
    time.sleep(1)

    fill_credentials(driver)
    time.sleep(0.5)

    click_login(driver)

    # Run the agent
    agent_process = start_agent()

    print("\n[=== AUTOMATION RUNNING ===]")
    print("Chrome is open, CAPTCHA popup should be visible.")
    print("Agent script is active and solving now.")

if __name__ == "__main__":
    main()

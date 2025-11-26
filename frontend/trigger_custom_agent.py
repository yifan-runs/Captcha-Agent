#!/usr/bin/env python3
import subprocess
import random
import string
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options

# ------------------------------
# Utility: random string
# ------------------------------
def random_string(n=8):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=n))

# ------------------------------
# Step 1: Launch Chrome + Login Page
# ------------------------------
def launch_login_page(url=" http://127.0.0.1:5000"):
    chrome_options = Options()
    chrome_options.add_experimental_option("detach", True)   # keep chrome open

    driver = webdriver.Chrome(options=chrome_options)
    driver.get(url)
    return driver

# ------------------------------
# Step 2: Fill username & password
# ------------------------------
def fill_credentials(driver):
    user = random_string()
    password = random_string()

    driver.find_element(By.ID, "username").send_keys(user)
    driver.find_element(By.ID, "password").send_keys(password)

    print(f"[+] Entered username={user}, pwd={password}")

# ------------------------------
# Step 3: Click the Login button 
# (this opens the CAPTCHA popup window)
# ------------------------------
def click_login(driver):
    driver.find_element(By.TAG_NAME, "button").click()
    print("[+] Login clicked - CAPTCHA window should open")

    # Give small delay for popup to appear
    time.sleep(1.5)

# ------------------------------
# Step 4: Start captcha-solving agent
# ------------------------------
def start_agent():
    print("[+] Starting custom agent...")
    p = subprocess.Popen(["/usr/bin/python3", "/Users/amarvijs/Projects/TCD/sc/mainProject2/frontend/custom_agent_browser.py"])
    print("[+] Agent started with PID:", p.pid)
    return p

# ------------------------------
# MAIN WORKFLOW
# ------------------------------
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
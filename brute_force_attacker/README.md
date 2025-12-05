# Final Version: version4_pro-pi & frontend2

## 1. Project Overview: A Brute Force Testing Tool

This project is an automated testing script based on **Python + Selenium + Chromium**, designed for:

* Performing automated interaction testing on **CAPTCHA pages that we have built ourselves**
* Using multiple "brute force" style interaction strategies to test how the CAPTCHA component behaves under different interaction paths, and to verify whether the system’s response and protection logic are robust

---

## 2. Features: Auto Launch + Auto Screenshot

**Automatic Launch of Chromium Browser**

    The script automatically starts a Chromium browser instance controlled by Selenium to load and test your local CAPTCHA page.

    Main purposes:

    * Eliminate the need for manual browser operations
    * Ensure the testing process is reproducible and scriptable
    * Make it easy to reproduce issues on different devices (e.g. PC / Raspberry Pi)

**Automatic Screenshot Saving (for Observing the Process)**

    The script automatically saves screenshots at several key stages, such as:

    * After the page finishes loading
    * After the Canvas has been rendered
    * Before and after each interaction attempt
    * When failures or exceptions occur

    These screenshots help visualize the testing process and assist with debugging.

---

## 3. Canvas Pixel Analysis for Bubble Position Detection

This project uses an **HTML5 Canvas CAPTCHA**.
The script includes basic pixel analysis logic for the Canvas, used to:

* Extract approximate distributions of “bubble areas” from the Canvas pixel data
* Verify whether the page renders target elements correctly
* Support research on Canvas behavior in automated testing scenarios

This is aimed at analyzing our own system's rendering and interaction logic, not bypassing external services.

---

## 4. Multiple Click Strategies

The project implements multiple interaction strategies to simulate different user behaviors and evaluate system response:

| Strategy         | Description                                               |
| ---------------- | --------------------------------------------------------- |
| `smallest_first` | Simulates clicking smaller objects first                  |
| `largest_first`  | Simulates clicking larger objects first                   |
| `mixed`          | Mixed strategy combining small, medium, and large targets |

These strategies are part of **test-driven development (TDD)** and **system robustness testing**.

---

## 5. Automatic Result Detection + Error Handling + Safe Shutdown

**Automatic Success Detection**

    After executing a strategy, the script automatically checks whether the page state has changed, for example:

    * Whether success-related messages appear
    * Whether the target Canvas disappears or is replaced
    * Whether the page enters a new state

**Error Handling Mechanism**

    When encountering issues such as:

    * Browser startup failure
    * Page loading errors
    * Elements not found
    * Canvas parsing failures

    The script will not crash immediately. Instead, it will:

    * Output clear error logs
    * Save the current screenshot
    * Exit safely

**Safe Browser Shutdown**

    Regardless of whether the test succeeds or fails, the script ensures:

    * Proper shutdown of the browser instance
    * Release of system resources
    * Prevention of leftover background processes or port locking

    This is particularly important when running on Raspberry Pi or server environments.

---

## 6. How to Use (Example)

**a. Install Dependencies**

    Make sure the following are installed:

    * Python 3.x
    * Selenium
    * Chromium / Chrome browser
    * Matching version of ChromeDriver

run install.sh

---

**b. Start Your Local CAPTCHA Page**

For example, if you run a Flask server:

```bash
python app.py
```

Make sure it can be accessed via:

```
http://127.0.0.1:5000/captcha
```

---

**c. Run the Script**

In the project directory, execute:

```bash
python run_attacker.py
```

The script will:

1. Start the browser
2. Open your local CAPTCHA page
3. Execute multiple interaction testing strategies
4. Save screenshots and logs
5. Safely close the browser

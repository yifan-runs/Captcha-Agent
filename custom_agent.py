#run captcha_bubbles_v1.py first and then run this file
import pygetwindow as gw
import pyautogui
import pytesseract
import time
import re

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

instruction_text = None

def ocr_read_hud(title="Anti-AI Bubble CAPTCHA", max_attempts=10):
    """
    Reads the HUD area of the CAPTCHA window and extracts:
      - no_of_bubbles: 2 or 3
      - bubble_order: "ascending" or "descending"
    Retries OCR until successful.
    """
    global instruction_text
    
    # If we've already read it successfully once
    if instruction_text is not None:
        return instruction_text

    attempt = 0
    extracted = False

    while not extracted and attempt < max_attempts:
        attempt += 1
        print(f"OCR attempt {attempt}/{max_attempts}...")

        # Find CAPTCHA window
        windows = gw.getWindowsWithTitle(title)
        if not windows:
            print("CAPTCHA window not found yet — retrying...")
            time.sleep(1)
            continue

        win = windows[0]
        win.activate()

        TITLE_BAR_HEIGHT = 30
        BORDER = 0
        HUD_HEIGHT = 80  # Taller region to capture both title + instruction

        x, y, w, h = win.left, win.top, win.width, win.height

        # HUD region inside game window
        hud_region = (
            x + 10 + BORDER,
            y + 6 + TITLE_BAR_HEIGHT,
            w - 20 - 2 * BORDER,
            HUD_HEIGHT
        )

        img = pyautogui.screenshot(region=hud_region)
        text = pytesseract.image_to_string(img).strip()

        print("OCR reads:\n", text, "\n")

        # Try extracting:
        #  - number: "2" or "3"
        #  - order: "ascending" or "descending"
        number_match = re.search(r"\b(2|3)\b", text)
        order_match = re.search(r"\b(ascending|descending)\b", text, re.IGNORECASE)

        if number_match and order_match:
            no_of_bubbles = int(number_match.group(1))
            bubble_order = order_match.group(1).lower()

            instruction_text = {
                "text": text,
                "no_of_bubbles": no_of_bubbles,
                "bubble_order": bubble_order
            }
            print("✔ Extracted successfully:")
            print("   no_of_bubbles =", no_of_bubbles)
            print("   bubble_order  =", bubble_order)
            return instruction_text

        print("❌ Extraction failed — retrying...\n")
        time.sleep(1)

    print("❌ Failed to extract instruction after retries.")
    return no_of_bubbles, bubble_order


if __name__ == "__main__":
    print("Waiting for CAPTCHA window...")
    time.sleep(2)

    result = ocr_read_hud()

    print("\nFinal instruction result:", result)

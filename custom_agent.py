import pygetwindow as gw
import pyautogui
import pytesseract
import time

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
instruction_text = None

def read_instruction_from_captcha_window(title="Anti-AI Bubble CAPTCHA"):
    global instruction_text
    if instruction_text is not None:
        return instruction_text

    windows = gw.getWindowsWithTitle(title)
    if not windows:
        print("CAPTCHA window not found!")
        return ""
    
    captcha_win = windows[0]
    captcha_win.activate()  # bring it to front

    # Approximate offsets to skip title bar and borders
    TITLE_BAR_HEIGHT = 50
    BORDER_WIDTH = 0

    x, y, w, h = captcha_win.left, captcha_win.top, captcha_win.width, captcha_win.height

    HUD_HEIGHT = 56
    hud_region = (
        x + 10 + BORDER_WIDTH,
        y + 6 + TITLE_BAR_HEIGHT,
        w - 20 - 2*BORDER_WIDTH,
        HUD_HEIGHT
    )

    # Screenshot HUD
    hud_img = pyautogui.screenshot(region=hud_region)
    text = pytesseract.image_to_string(hud_img).strip()
    instruction_text = text
    print("OCR reads:", instruction_text)
    return instruction_text


if __name__ == "__main__":
    print("Waiting for CAPTCHA window...")
    time.sleep(2.5)
    read_instruction_from_captcha_window()

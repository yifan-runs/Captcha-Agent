from PIL import Image
import pytesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

img = Image.new("RGB", (100, 30), color=(255, 255, 255))
text = pytesseract.image_to_string(img)
print("OCR test output:", text)

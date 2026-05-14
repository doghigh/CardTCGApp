import cv2
import re
import os
from typing import Dict

try:
    import pytesseract
    HAS_TESSERACT = True
except ImportError:
    HAS_TESSERACT = False


class CardIdentifier:
    """OCR-based card information extraction with improved preprocessing."""

    def __init__(self):
        """Auto-detect and configure Tesseract path."""
        if not HAS_TESSERACT:
            return

        # Common Tesseract installation paths
        common_paths = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            "/usr/bin/tesseract",
            "/usr/local/bin/tesseract",
        ]

        # Check environment variable first
        env_path = os.environ.get('TESSERACT_CMD')
        if env_path and os.path.exists(env_path):
            pytesseract.pytesseract.tesseract_cmd = env_path
            return

        # Auto-detect
        for path in common_paths:
            if os.path.exists(path):
                pytesseract.pytesseract.tesseract_cmd = path
                break

    def extract_text(self, img: np.ndarray) -> str:
        """Extract text from card image with optimized preprocessing."""
        if not HAS_TESSERACT or img is None or img.size == 0:
            return ""

        try:
            # Convert to grayscale
            if len(img.shape) == 3:
                gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
            else:
                gray = img

            # Resize for better OCR accuracy
            height, width = gray.shape
            scale = max(1.8, 900 / width)  # Target \~900px width
            gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

            # Strong preprocessing for trading cards
            gray = cv2.GaussianBlur(gray, (3, 3), 0)
            _, gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            gray = cv2.medianBlur(gray, 3)

            # OCR configuration optimized for cards
            custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789:/-.,# '
            text = pytesseract.image_to_string(gray, config=custom_config).strip()

            return text

        except Exception as e:
            print(f"OCR Error: {e}")
            return ""

    def parse_card_info(self, front_text: str = "", back_text: str = "") -> Dict:
        """Parse card details from OCR text (supports front + back)."""
        info = {
            'name': None,
            'set_name': None,
            'card_number': None,
            'rarity': None
        }

        combined = (front_text + "\n" + back_text).strip()
        if not combined:
            return info

        lines = [line.strip() for line in combined.split('\n') if line.strip()]

        # Card number patterns (very common)
        for line in lines:
            num_match = re.search(r'(\d{1,4})\s*[/-]?\s*(\d{1,4})', line)
            if num_match and not info['card_number']:
                info['card_number'] = num_match.group(0)
                break

        # Rarity
        rarity_pattern = r'\b(R|M|U|C|SR|UR|SEC|PR|SP|RR|CHR|Rare|Common|Uncommon)\b'
        for line in lines:
            if re.search(rarity_pattern, line, re.I):
                info['rarity'] = line.split()[-1] if len(line.split()) > 1 else line
                break

        # Name (longest title-like line)
        for line in lines:
            if len(line) > 8 and not re.search(r'^\d', line) and len(line.split()) > 1:
                if not info['name'] or len(line) > len(info.get('name', '')):
                    info['name'] = line[:120]
                    break

        # Set name fallback
        for line in lines[:20]:
            if 4 <= len(line) <= 40 and re.search(r'[A-Z]{3,}', line) and not any(
                    x in line.lower() for x in ['copyright', 'illustration', 'artist', 'tm']):
                if not info['set_name']:
                    info['set_name'] = line[:40]
                    break

        # Final fallback
        if not info['name'] and lines:
            info['name'] = lines[0][:120]

        return info
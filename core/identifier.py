import cv2
import re
import os
import numpy as np
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
        """Extract text from card image using multiple preprocessing strategies."""
        if not HAS_TESSERACT or img is None or img.size == 0:
            return ""

        try:
            if len(img.shape) == 3:
                gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
            else:
                gray = img.copy()

            height, width = gray.shape
            scale = max(1.5, 800 / width)
            gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

            results = []
            config = r'--oem 3 --psm 6'

            # Strategy 1: adaptive threshold (handles colored backgrounds)
            adapt = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                          cv2.THRESH_BINARY, 31, 10)
            results.append(pytesseract.image_to_string(adapt, config=config).strip())

            # Strategy 2: Otsu on denoised
            blur = cv2.GaussianBlur(gray, (3, 3), 0)
            _, otsu = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            results.append(pytesseract.image_to_string(otsu, config=config).strip())

            # Strategy 3: inverted adaptive
            adapt_inv = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                              cv2.THRESH_BINARY_INV, 31, 10)
            results.append(pytesseract.image_to_string(adapt_inv, config=config).strip())

            best = max(results, key=lambda t: sum(1 for w in t.split() if len(w) >= 3 and w.isalpha()))
            return best

        except Exception as e:
            print(f"OCR Error: {e}")
            return ""

    def extract_header_text(self, img: np.ndarray) -> str:
        """Extract text from the top ~25% of an image (card header / player name area).

        Uses individual color channels so white-on-red or white-on-dark headers
        survive thresholding — pure grayscale loses contrast on colored backgrounds.
        """
        if not HAS_TESSERACT or img is None or img.size == 0:
            return ""

        try:
            h, w = img.shape[:2]
            header = img[:max(h // 4, 60), :]

            scale = max(2.0, 800 / w)
            config = r'--oem 3 --psm 6'
            results = []

            if len(header.shape) == 3:
                channels = [
                    header[:, :, 0],  # R
                    header[:, :, 1],  # G
                    header[:, :, 2],  # B
                    cv2.cvtColor(header, cv2.COLOR_RGB2GRAY),
                ]
            else:
                channels = [header]

            for ch in channels:
                resized = cv2.resize(ch, None, fx=scale, fy=scale,
                                     interpolation=cv2.INTER_CUBIC)
                for inv in (False, True):
                    mode = cv2.THRESH_BINARY_INV if inv else cv2.THRESH_BINARY
                    _, thresh = cv2.threshold(resized, 0, 255,
                                              mode | cv2.THRESH_OTSU)
                    t = pytesseract.image_to_string(thresh, config=config).strip()
                    if t:
                        results.append(t)

            if not results:
                return ""
            return max(results, key=lambda t: sum(
                1 for w in t.split() if len(w) >= 2 and w.isalpha()))

        except Exception as e:
            print(f"Header OCR Error: {e}")
            return ""

    def parse_card_info(self, front_text: str = "", back_text: str = "",
                        header_text: str = "") -> Dict:
        """Parse card details from OCR text (supports front + back)."""
        info = {
            'name': None,
            'set_name': None,
            'card_number': None,
            'rarity': None,
            'year': None,
            'game': None,
        }

        combined = (front_text + "\n" + back_text).strip()
        if not combined:
            return info

        lines = [line.strip() for line in combined.split('\n') if line.strip()]

        # --- Year extraction ---
        year_match = re.search(r'\b(19[5-9]\d|20[0-3]\d)\b', combined)
        if year_match:
            info['year'] = int(year_match.group(1))

        # --- Game detection ---
        lower = combined.lower()
        sports_signals = ['batting avg', 'slugging', 'strikeout', 'innings', 'touchdowns',
                          'rebounds', 'assists', 'goals', 'pts.', 'g ab r h', 'era',
                          'bats both', 'bats right', 'bats left', 'throws right', 'throws left',
                          'born ', 'ht.', 'wt.', 'height', 'weight']
        tcg_signals = ['energy', 'trainer', 'item', 'mana cost', 'converted mana',
                       'flying', 'trample', 'haste', 'summon', 'destroy target',
                       'hp ', 'weakness', 'resistance', 'retreat', 'life points']
        sports_score = sum(1 for s in sports_signals if s in lower)
        tcg_score = sum(1 for s in tcg_signals if s in lower)
        if sports_score > tcg_score:
            # Distinguish sport type
            if any(x in lower for x in ['batting', 'strikeout', 'rbi', 'innings', 'era', 'g ab']):
                info['game'] = 'Baseball'
            elif any(x in lower for x in ['rebounds', 'assists', 'field goal', 'three-point']):
                info['game'] = 'Basketball'
            elif any(x in lower for x in ['touchdowns', 'rushing', 'receiving', 'quarterback']):
                info['game'] = 'Football'
            elif any(x in lower for x in ['goals', 'penalty', 'power play', 'goalie']):
                info['game'] = 'Hockey'
            else:
                info['game'] = 'Sports Cards'
        elif tcg_score > 0:
            if any(x in lower for x in ['mana', 'summon', 'enchantment', 'artifact', 'sorcery', 'instant']):
                info['game'] = 'Magic: The Gathering'
            elif any(x in lower for x in ['hp', 'pokemon', 'pokémon', 'trainer', 'energy']):
                info['game'] = 'Pokémon'
            elif any(x in lower for x in ['life points', 'atk/', 'def/', 'tribute']):
                info['game'] = 'Yu-Gi-Oh!'

        # --- Card number ---
        for line in lines:
            num_match = re.search(r'(?:No\.|#|Card\s*#?)\s*(\d{1,4})', line, re.I)
            if num_match and not info['card_number']:
                info['card_number'] = num_match.group(1)
                break
        if not info['card_number']:
            # Standalone number on its own line
            for line in lines:
                if re.fullmatch(r'\d{1,4}', line) and not info['card_number']:
                    info['card_number'] = line
                    break
        if not info['card_number'] and header_text:
            # Number in header (e.g. Fleer set number in logo circle)
            m = re.search(r'\b(\d{1,4})\b', header_text)
            if m:
                info['card_number'] = m.group(1)

        # --- Rarity (require multi-char tokens to avoid noise) ---
        rarity_pattern = r'\b(SR|UR|SEC|PR|SP|RR|CHR|Rare|Common|Uncommon)\b'
        for line in lines:
            m = re.search(rarity_pattern, line, re.I)
            if m:
                info['rarity'] = m.group(1)
                break

        # --- Name: header text takes highest priority (dedicated region OCR) ---
        header_lines = [ln.strip() for ln in header_text.split('\n') if ln.strip()] if header_text else []
        header_caps = [
            ln for ln in header_lines
            if 1 <= len(ln.split()) <= 5
            and all(c.isalpha() or c.isspace() for c in ln)
            and len(ln) >= 4
        ]
        if header_caps:
            # Prefer all-caps; otherwise take first clean alpha line
            all_caps = [ln for ln in header_caps if ln.isupper()]
            info['name'] = (all_caps or header_caps)[0]

        # Fallback: all-caps line from combined body text
        if not info['name']:
            caps_candidates = [
                ln for ln in lines
                if 2 <= len(ln.split()) <= 5
                and ln.isupper()
                and all(c.isalpha() or c.isspace() for c in ln)
                and len(ln) >= 5
            ]
            if caps_candidates:
                info['name'] = caps_candidates[0]

        # Last resort: title-case short line
        if not info['name']:
            for line in lines:
                words = line.split()
                if 2 <= len(words) <= 6 and not re.search(r'^\d', line):
                    alpha_ratio = sum(1 for c in line if c.isalpha()) / max(len(line), 1)
                    if alpha_ratio > 0.7:
                        info['name'] = line[:80]
                        break

        # --- Set name ---
        set_exclude = ['copyright', '©', 'illustration', 'artist', 'tm', 'printed', 'corp']
        for line in lines[:25]:
            if (4 <= len(line) <= 40
                    and re.search(r'[A-Za-z]{3,}', line)
                    and not any(x in line.lower() for x in set_exclude)
                    and line != info.get('name')):
                info['set_name'] = line[:40]
                break

        if not info['name'] and lines:
            info['name'] = lines[0][:80]

        return info

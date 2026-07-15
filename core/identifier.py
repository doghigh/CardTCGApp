import base64
import json
import re
import os
import logging
import cv2
import numpy as np
from typing import Dict, Optional

from core import trial

logger = logging.getLogger(__name__)

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

try:
    import pytesseract
    HAS_TESSERACT = True
except ImportError:
    HAS_TESSERACT = False


VISION_PROMPT = """You are a trading card expert. Examine this card image and extract the fields below.
Respond with ONLY a JSON object — no markdown, no commentary.

Fields:
- name: the card's TITLE — the text in the title bar at the very TOP of the card.
    * Magic cards: the card name printed at the top. Do NOT use the type line
      (e.g. "Summon Creature", "Summon Elf", "Summon Wall", "Creature — Elf",
      "Artifact", "Instant"). The type line sits in the MIDDLE of the card,
      below the art, and is NEVER the name.
    * Sports cards: the player's name.
- set_name: a complete, self-contained set label — NOT just a brand name.
    * Sports cards: "<year> <brand>", e.g. "1987 Topps", "1990 Upper Deck",
      "1988 Donruss", "1991 Fleer". Put the year FIRST. The brand alone (just
      "Topps") is NOT an acceptable label — always include the year.
    * TCG (Magic, Pokémon, Yu-Gi-Oh!, etc.): the full expansion / set name,
      e.g. "Tempest", "Fallen Empires", "Amonkhet", "Kaladesh". Prefer the full
      set name over a set code (use "Amonkhet", not "AKH").
    NEVER put the game's name (e.g. "Magic: The Gathering") in this field.
    If you cannot clearly identify the set, use null.
- card_number: the collector number exactly as printed (often a bottom corner,
    e.g. "86", "011/011", "4/5"), else null.
- rarity: rarity if shown (Common / Uncommon / Rare / Mythic, or a sports
    insert label), else null.
- year: 4-digit year as an integer if visible (often in the bottom copyright
    line), else null.
- game: one of "Baseball", "Basketball", "Football", "Hockey",
    "Magic: The Gathering", "Pokémon", "Yu-Gi-Oh!", "One Piece", "Lorcana",
    "Sports Cards", "Non-Sport" (entertainment/TV/movie cards such as Star Wars,
    Garbage Pail Kids, Marvel), or "Other".

Important:
- Older Magic cards (pre-2003) print the type as "Summon <type>". Ignore that
  line completely when choosing the name — read the title bar at the top.
- A token's name is its creature/permanent name at the top (e.g. "Plant").
- If a field is unreadable or absent, use null rather than guessing.

Example: {"name": "Elvish Farmer", "set_name": "Fallen Empires", "card_number": null, "rarity": "Common", "year": 1994, "game": "Magic: The Gathering"}

Also grade the card's physical condition from the image(s):
- condition_score: an integer 0-100 using this scale:
    95-100 Gem Mint (pristine); 88-94 Mint; 76-87 Near Mint (light wear);
    64-75 Excellent; 52-63 Very Good; 40-51 Good; 25-39 Played;
    0-24 Poor. IMPORTANT: if any material is missing — a torn or chipped
    corner/edge, or exposed cardboard — the card is AT MOST Good (<=51), and
    large tears/missing chunks are Poor. Heavy creasing or staining is
    Excellent or lower.
- defects: a list (possibly empty) of {"type","location","severity"} where
    type is one of "missing_material","corner_damage","edge_wear",
    "surface_crease","surface_scratch","staining","print_defect",
    "off_centering"; location is one of "top_left","top_right","bottom_left",
    "bottom_right","top","bottom","left","right","center"; severity is
    "minor","moderate", or "severe".
Include condition_score and defects as additional fields in the SAME JSON object."""


class CardIdentifier:
    """Card identification via Claude vision API, with Tesseract OCR fallback."""

    def __init__(self):
        self._anthropic: Optional[object] = None
        self._init_tesseract()

    def _init_tesseract(self):
        if not HAS_TESSERACT:
            return
        common_paths = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            "/usr/bin/tesseract",
            "/usr/local/bin/tesseract",
        ]
        env_path = os.environ.get('TESSERACT_CMD')
        if env_path and os.path.exists(env_path):
            pytesseract.pytesseract.tesseract_cmd = env_path
            return
        for path in common_paths:
            if os.path.exists(path):
                pytesseract.pytesseract.tesseract_cmd = path
                break

    def _resolve_client(self):
        """Return (client, mode). mode is 'own', 'trial', or 'none'.

        'own'  — user supplied ANTHROPIC_API_KEY; call Anthropic directly.
        'trial'— no user key but trial credits remain; route via the Worker.
        'none' — no key and no trial credits left.
        """
        if not HAS_ANTHROPIC:
            return None, 'none'
        api_key = os.environ.get('ANTHROPIC_API_KEY')
        if api_key:
            if self._anthropic is None:
                self._anthropic = anthropic.Anthropic(api_key=api_key)
            return self._anthropic, 'own'
        if trial.trial_remaining() > 0:
            # Placeholder key — the Worker injects the real one. base_url is the
            # Worker origin; the SDK appends "/v1/messages".
            client = anthropic.Anthropic(api_key='trial-proxy',
                                         base_url=trial.WORKER_BASE_URL)
            return client, 'trial'
        return None, 'none'

    def reload_credentials(self):
        """Drop the cached client so the next call picks up a new API key."""
        self._anthropic = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def identify_card(self, front_img: np.ndarray,
                      back_img: Optional[np.ndarray] = None) -> Dict:
        """Identify a card. See module docstring for 'source' semantics.

        'source' is one of: 'claude' (genuine vision id, direct or trial-proxied),
        'ocr' (degraded Tesseract fallback), or a 'trial_*' marker meaning the
        trial is blocked and the UI should offer the add-your-own-key dialog.
        """
        _, mode = self._resolve_client()

        if mode == 'none':
            return self._trial_blocked('trial_exhausted')

        if mode == 'trial':
            try:
                result = self._identify_with_claude(front_img, back_img)
            except trial.TrialCapacityReached:
                return self._trial_blocked('trial_capacity')
            except trial.TrialUnavailable:
                return self._trial_blocked('trial_unavailable')
            if result and result.get('name'):
                trial.consume_trial()
                result['source'] = 'claude'
                return result
            # Reached the proxy but got no usable data — treat as unavailable,
            # do not consume a credit, do not fabricate via OCR.
            return self._trial_blocked('trial_unavailable')

        # mode == 'own': existing behavior, unchanged.
        result = self._identify_with_claude(front_img, back_img)
        if result and result.get('name'):
            result['source'] = 'claude'
            return result

        # OCR fallback — degraded mode. Only the (header-OCR) name is reasonably
        # reliable; set/number/rarity are not, so parse_card_info no longer
        # fabricates them. Flagged 'ocr' so callers can warn / avoid clobbering.
        front_text = self.extract_text(front_img)
        back_text = self.extract_text(back_img) if back_img is not None else ""
        header_text = self.extract_header_text(back_img) if back_img is not None else ""
        info = self.parse_card_info(front_text, back_text, header_text)
        info['source'] = 'ocr'
        return info

    @staticmethod
    def _trial_blocked(reason: str) -> Dict:
        return {'name': None, 'set_name': None, 'card_number': None,
                'rarity': None, 'year': None, 'game': None, 'source': reason}

    # ------------------------------------------------------------------
    # Claude vision
    # ------------------------------------------------------------------

    def _identify_with_claude(self, front_img: np.ndarray,
                               back_img: Optional[np.ndarray] = None,
                               client=None, trial_mode: bool = False) -> Optional[Dict]:
        if client is None:
            client, mode = self._resolve_client()
            trial_mode = (mode == 'trial')
        if client is None:
            return None
        try:
            content = []
            for img in ([front_img] if back_img is None else [front_img, back_img]):
                b64 = self._img_to_base64(img)
                if b64:
                    content.append({
                        "type": "image",
                        "source": {"type": "base64", "media_type": "image/jpeg", "data": b64}
                    })
            if not content:
                return None
            content.append({"type": "text", "text": VISION_PROMPT})

            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=512,
                messages=[{"role": "user", "content": content}]
            )
            raw = response.content[0].text.strip()
            # Strip markdown code fences if present
            raw = re.sub(r'^```[a-z]*\n?', '', raw)
            raw = re.sub(r'\n?```$', '', raw)
            data = json.loads(raw)

            # Defensive cleanup: never let the game name leak into set_name
            set_name = data.get('set_name') or None
            if set_name and set_name.strip().lower() in {
                "magic: the gathering", "magic the gathering", "magic", "mtg",
                "pokemon", "pokémon", "yu-gi-oh!", "yugioh",
            }:
                set_name = None

            condition = None
            cs = data.get('condition_score')
            if isinstance(cs, bool):
                cs = None
            if isinstance(cs, (int, float)) or (isinstance(cs, str) and cs.strip().lstrip('-').isdigit()):
                score = max(0, min(100, int(float(cs))))
                defects = data.get('defects')
                if not isinstance(defects, list):
                    defects = []
                condition = {'score': score, 'defects': defects}

            return {
                'name': data.get('name') or None,
                'set_name': set_name,
                'card_number': str(data['card_number']) if data.get('card_number') else None,
                'rarity': data.get('rarity') or None,
                'year': int(data['year']) if data.get('year') else None,
                'game': data.get('game') or None,
                'condition': condition,
            }
        except Exception as e:
            if trial_mode:
                status = getattr(e, "status_code", None)
                body = getattr(e, "body", None)
                etype = ""
                if isinstance(body, dict):
                    etype = (body.get("error") or {}).get("type", "")
                if status == 429 and etype == "trial_capacity":
                    raise trial.TrialCapacityReached() from e
                raise trial.TrialUnavailable() from e
            logger.warning("Claude vision error: %s", e)
            return None

    def _img_to_base64(self, img: np.ndarray) -> Optional[str]:
        if img is None or img.size == 0:
            return None
        try:
            bgr = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
            # Resize if very large to keep API payload reasonable
            h, w = bgr.shape[:2]
            if max(h, w) > 1600:
                scale = 1600 / max(h, w)
                bgr = cv2.resize(bgr, None, fx=scale, fy=scale,
                                 interpolation=cv2.INTER_AREA)
            ok, buf = cv2.imencode('.jpg', bgr, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if not ok:
                return None
            return base64.standard_b64encode(buf.tobytes()).decode('ascii')
        except Exception as e:
            logger.warning("Image encode error: %s", e)
            return None

    # ------------------------------------------------------------------
    # OCR fallback (Tesseract)
    # ------------------------------------------------------------------

    def extract_text(self, img: np.ndarray) -> str:
        if not HAS_TESSERACT or img is None or img.size == 0:
            return ""
        try:
            if len(img.shape) == 3:
                gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
            else:
                gray = img.copy()

            h, w = gray.shape
            scale = max(1.5, 800 / w)
            gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

            config = r'--oem 3 --psm 6'
            results = []

            adapt = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                          cv2.THRESH_BINARY, 31, 10)
            results.append(pytesseract.image_to_string(adapt, config=config).strip())

            blur = cv2.GaussianBlur(gray, (3, 3), 0)
            _, otsu = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            results.append(pytesseract.image_to_string(otsu, config=config).strip())

            adapt_inv = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                              cv2.THRESH_BINARY_INV, 31, 10)
            results.append(pytesseract.image_to_string(adapt_inv, config=config).strip())

            return max(results, key=lambda t: sum(1 for w in t.split() if len(w) >= 3 and w.isalpha()))
        except Exception as e:
            logger.debug("OCR error: %s", e)
            return ""

    def extract_header_text(self, img: np.ndarray) -> str:
        if not HAS_TESSERACT or img is None or img.size == 0:
            return ""
        try:
            h, w = img.shape[:2]
            hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV)
            row_sat = hsv[:, :, 1].mean(axis=1)
            top = int(h * 0.40)
            top_sat = row_sat[:top]
            thresh = max(top_sat.mean() + top_sat.std(), 60)
            saturated_rows = np.where(top_sat > thresh)[0]

            if len(saturated_rows) >= 4:
                r0 = max(0, int(saturated_rows[0]) - 4)
                r1 = min(h, int(saturated_rows[-1]) + 9)
                header = img[r0:r1, :]
            else:
                header = img[:max(h // 5, 40), :]

            if header.shape[0] < 8:
                header = img[:max(h // 5, 40), :]

            scale = max(3.0, 1200 / w)
            header_big = cv2.resize(header, None, fx=scale, fy=scale,
                                    interpolation=cv2.INTER_CUBIC)

            channels = [header_big[:, :, i] for i in range(3)]
            channels.append(cv2.cvtColor(header_big, cv2.COLOR_RGB2GRAY))
            best_ch = max(channels, key=lambda c: float(c.std()))

            results = []
            for inv in (False, True):
                mode = cv2.THRESH_BINARY_INV if inv else cv2.THRESH_BINARY
                blurred = cv2.GaussianBlur(best_ch, (3, 3), 0)
                _, thr = cv2.threshold(blurred, 0, 255, mode | cv2.THRESH_OTSU)
                kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
                thr = cv2.morphologyEx(thr, cv2.MORPH_CLOSE, kernel)
                for psm in ('7', '6'):
                    t = pytesseract.image_to_string(thr, config=f'--oem 3 --psm {psm}').strip()
                    if t:
                        results.append(t)

            if not results:
                return ""
            return max(results, key=lambda t: sum(
                1 for word in t.split() if len(word) >= 2 and word.isalpha()))
        except Exception as e:
            logger.debug("Header OCR error: %s", e)
            return ""

    def parse_card_info(self, front_text: str = "", back_text: str = "",
                        header_text: str = "") -> Dict:
        """Parse card details from OCR text. Used as fallback when vision API unavailable."""
        info = {
            'name': None, 'set_name': None, 'card_number': None,
            'rarity': None, 'year': None, 'game': None,
        }

        combined = (front_text + "\n" + back_text).strip()
        if not combined:
            return info

        lines = [ln.strip() for ln in combined.split('\n') if ln.strip()]

        year_m = re.search(r'\b(19[5-9]\d|20[0-3]\d)\b', combined)
        if year_m:
            info['year'] = int(year_m.group(1))

        lower = combined.lower()
        sports_signals = ['batting avg', 'slugging', 'strikeout', 'innings', 'touchdowns',
                          'rebounds', 'assists', 'goals', 'g ab r h', 'era',
                          'bats both', 'bats right', 'bats left', 'throws right', 'throws left']
        tcg_signals = ['energy', 'trainer', 'mana cost', 'flying', 'trample', 'haste',
                       'summon', 'destroy target', 'weakness', 'resistance', 'retreat', 'life points']
        sports_score = sum(1 for s in sports_signals if s in lower)
        tcg_score = sum(1 for s in tcg_signals if s in lower)
        if sports_score > tcg_score:
            if any(x in lower for x in ['batting', 'strikeout', 'rbi', 'era', 'g ab']):
                info['game'] = 'Baseball'
            elif any(x in lower for x in ['rebounds', 'assists', 'field goal']):
                info['game'] = 'Basketball'
            elif any(x in lower for x in ['touchdowns', 'rushing', 'quarterback']):
                info['game'] = 'Football'
            elif any(x in lower for x in ['goals', 'penalty', 'power play']):
                info['game'] = 'Hockey'
            else:
                info['game'] = 'Sports Cards'
        elif tcg_score > 0:
            if any(x in lower for x in ['mana', 'summon', 'enchantment', 'sorcery', 'instant']):
                info['game'] = 'Magic: The Gathering'
            elif any(x in lower for x in ['pokemon', 'pokémon', 'trainer', 'weakness']):
                info['game'] = 'Pokémon'
            elif any(x in lower for x in ['life points', 'atk/', 'def/', 'tribute']):
                info['game'] = 'Yu-Gi-Oh!'

        for line in lines:
            m = re.search(r'(?:No\.|#|Card\s*#?)\s*(\d{1,4})', line, re.I)
            if m and not info['card_number']:
                info['card_number'] = m.group(1)
                break
        # NOTE: no bare-digit / header-digit card_number fallback, and no
        # short-code rarity guess — on degraded OCR these match noise and
        # pollute the record (garbage card numbers / "Sp"/"RR" rarities).
        # Leave them null; Claude fills them reliably when available.

        header_lines = [ln.strip() for ln in header_text.split('\n') if ln.strip()] if header_text else []
        header_caps = [ln for ln in header_lines
                       if 1 <= len(ln.split()) <= 5
                       and all(c.isalpha() or c.isspace() for c in ln)
                       and len(ln) >= 4]
        if header_caps:
            all_caps = [ln for ln in header_caps if ln.isupper()]
            info['name'] = (all_caps or header_caps)[0]

        if not info['name']:
            caps = [ln for ln in lines
                    if 2 <= len(ln.split()) <= 5 and ln.isupper()
                    and all(c.isalpha() or c.isspace() for c in ln) and len(ln) >= 5]
            if caps:
                info['name'] = caps[0]

        if not info['name']:
            for line in lines:
                words = line.split()
                if 2 <= len(words) <= 6 and not re.search(r'^\d', line):
                    if sum(1 for c in line if c.isalpha()) / max(len(line), 1) > 0.7:
                        info['name'] = line[:80]
                        break

        # NOTE: set_name is intentionally NOT guessed from OCR text. On worn or
        # set-symbol-less cards this just grabbed a random body line (flavour
        # text, type line) and wrote garbage into the Set column. Leave it null.

        if not info['name'] and lines:
            info['name'] = lines[0][:80]

        return info

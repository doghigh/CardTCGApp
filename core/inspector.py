"""
Card condition inspector — calibrated for flatbed scanner input (300-600 DPI).

Thresholds are tuned for scanner output where:
  - Scanner bed bleeds white into image borders
  - Card sits on white/light background
  - Corner tips show natural white even on mint cards
  - High resolution means small real defects are visible
"""

import cv2
import numpy as np
from typing import List, Dict, Tuple


class CardInspector:
    """Computer vision based card condition grading."""

    GRADES = {
        'Gem Mint':  (95, 100),
        'Mint':      (88,  94),
        'Near Mint': (76,  87),
        'Excellent': (64,  75),
        'Very Good': (52,  63),
        'Good':      (40,  51),
        'Played':    (25,  39),
        'Poor':      (0,   24),
    }

    # ------------------------------------------------------------------ #
    #  Card region isolation                                               #
    # ------------------------------------------------------------------ #

    def _detect_card_region(self, img: np.ndarray) -> np.ndarray:
        """
        Crop to the card boundary, excluding scanner background.
        Uses a morphological approach to find the largest solid rectangle.
        """
        if img is None or img.size == 0:
            return img

        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY) if len(img.shape) == 3 else img.copy()
        h, w = gray.shape

        # Blur more aggressively to merge card body into one blob
        blurred = cv2.GaussianBlur(gray, (15, 15), 0)

        # Threshold: card is typically darker/more saturated than white scanner bed
        _, thresh = cv2.threshold(blurred, 240, 255, cv2.THRESH_BINARY_INV)

        # Close gaps so the card outline is solid
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (20, 20))
        closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return img

        # Pick the largest contour that looks like a card (aspect ratio ~0.7)
        best = None
        best_area = 0
        for c in contours:
            x, y, cw, ch = cv2.boundingRect(c)
            area = cw * ch
            aspect = min(cw, ch) / max(cw, ch) if max(cw, ch) > 0 else 0
            if area > best_area and aspect > 0.4 and cw > 80 and ch > 80:
                best_area = area
                best = (x, y, cw, ch)

        if best is None:
            return img

        x, y, cw, ch = best
        # Add a small inset so we don't analyse the scanner border edge
        inset = max(4, min(cw, ch) // 50)
        x  = max(0, x  + inset)
        y  = max(0, y  + inset)
        cw = min(w - x, cw - 2 * inset)
        ch = min(h - y, ch - 2 * inset)

        if cw < 50 or ch < 50:
            return img

        return img[y:y + ch, x:x + cw]

    # ------------------------------------------------------------------ #
    #  Corner analysis                                                     #
    # ------------------------------------------------------------------ #

    def _detect_corner_damage(self, img: np.ndarray) -> List[Dict]:
        """
        Detect corner whitening/fraying.
        Focuses on the corner TIP (small region at the extreme corner)
        rather than a large quadrant, to avoid false positives from card borders.
        """
        h, w = img.shape[:2]
        # Small tip region — at 400 DPI a real corner fray is tiny
        tip = max(6, min(h, w) // 20)   # ~50-70px at 400 DPI

        corners = {
            'top_left':     img[0:tip, 0:tip],
            'top_right':    img[0:tip, max(0, w - tip):w],
            'bottom_left':  img[max(0, h - tip):h, 0:tip],
            'bottom_right': img[max(0, h - tip):h, max(0, w - tip):w],
        }

        defects = []
        for name, region in corners.items():
            if region.size == 0:
                continue
            gray = (cv2.cvtColor(region, cv2.COLOR_RGB2GRAY)
                    if len(region.shape) == 3 else region)

            # White ratio — true corner damage shows significantly elevated whites
            white_ratio = np.sum(gray > 230) / gray.size

            # Edge roughness — fraying produces irregular high-frequency edges
            edges = cv2.Canny(gray, 40, 120)
            edge_density = np.sum(edges > 0) / max(edges.size, 1)

            # Calibrated thresholds (scanner corners are naturally bright)
            if white_ratio > 0.72:
                severity = 'severe' if white_ratio > 0.88 else 'moderate'
                defects.append({
                    'type': 'corner_whitening',
                    'location': name,
                    'severity': severity,
                    'metric': round(float(white_ratio), 3),
                })
            elif white_ratio > 0.58:
                defects.append({
                    'type': 'corner_whitening',
                    'location': name,
                    'severity': 'minor',
                    'metric': round(float(white_ratio), 3),
                })

            if edge_density > 0.45:
                defects.append({
                    'type': 'corner_fraying',
                    'location': name,
                    'severity': 'moderate' if edge_density > 0.60 else 'minor',
                    'metric': round(float(edge_density), 3),
                })

        return defects

    # ------------------------------------------------------------------ #
    #  Edge analysis                                                       #
    # ------------------------------------------------------------------ #

    def _detect_edge_wear(self, img: np.ndarray) -> List[Dict]:
        """Detect edge whitening along the four sides."""
        h, w = img.shape[:2]
        # Thin strip — scanner border is already excluded by inset in crop step
        thickness = max(4, min(h, w) // 50)

        regions = {
            'top':    img[0:thickness, :],
            'bottom': img[max(0, h - thickness):h, :],
            'left':   img[:, 0:thickness],
            'right':  img[:, max(0, w - thickness):w],
        }

        defects = []
        for name, region in regions.items():
            if region.size == 0:
                continue
            gray = (cv2.cvtColor(region, cv2.COLOR_RGB2GRAY)
                    if len(region.shape) == 3 else region)

            white_ratio = np.sum(gray > 230) / gray.size

            # Higher threshold than corners — edges are naturally brighter on cards
            if white_ratio > 0.65:
                severity = 'severe' if white_ratio > 0.82 else 'moderate'
                defects.append({
                    'type': 'edge_whitening',
                    'location': name,
                    'severity': severity,
                    'metric': round(float(white_ratio), 3),
                })
            elif white_ratio > 0.50:
                defects.append({
                    'type': 'edge_whitening',
                    'location': name,
                    'severity': 'minor',
                    'metric': round(float(white_ratio), 3),
                })

        return defects

    # ------------------------------------------------------------------ #
    #  Surface analysis                                                    #
    # ------------------------------------------------------------------ #

    def _detect_surface_defects(self, img: np.ndarray) -> List[Dict]:
        """Detect creases, scratches, and significant staining."""
        defects = []
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY) if len(img.shape) == 3 else img
        h, w = gray.shape

        # Crop inset to avoid card border lines triggering crease detection
        inset = max(10, min(h, w) // 12)
        center = gray[inset:h - inset, inset:w - inset]
        if center.size == 0:
            return defects

        # Crease / scratch detection — long straight lines through the card face
        edges = cv2.Canny(center, 50, 150)
        min_dim = min(center.shape[:2])
        lines = cv2.HoughLinesP(
            edges, 1, np.pi / 180,
            threshold=60,
            minLineLength=min_dim // 3,
            maxLineGap=15,
        )
        if lines is not None:
            long_lines = [
                l for l in lines
                if np.hypot(l[0][2] - l[0][0], l[0][3] - l[0][1]) > min_dim // 2.5
            ]
            if len(long_lines) >= 2:
                severity = 'severe' if len(long_lines) > 5 else 'moderate'
                defects.append({
                    'type': 'surface_crease',
                    'location': 'center',
                    'severity': severity,
                    'metric': len(long_lines),
                })

        # Staining — large dark patches on the card face
        if len(img.shape) == 3:
            hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV)
            val = hsv[:, :, 2]
            dark_ratio = np.sum(val < 40) / val.size
            if dark_ratio > 0.12:
                defects.append({
                    'type': 'surface_staining',
                    'location': 'center',
                    'severity': 'severe' if dark_ratio > 0.22 else 'moderate',
                    'metric': round(float(dark_ratio), 3),
                })

        return defects

    # ------------------------------------------------------------------ #
    #  Centering                                                           #
    # ------------------------------------------------------------------ #

    def _detect_centering(self, img: np.ndarray) -> Tuple[List[Dict], float]:
        """Calculate left/right and top/bottom centering."""
        h, w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY) if len(img.shape) == 3 else img

        # Look for the card image area (darker than the white border)
        _, thresh = cv2.threshold(gray, 220, 255, cv2.THRESH_BINARY_INV)

        col_proj = np.sum(thresh, axis=0).astype(float)
        row_proj = np.sum(thresh, axis=1).astype(float)

        def border_span(proj: np.ndarray):
            mx = proj.max()
            if mx < 1:
                return 0, len(proj)
            cutoff = mx * 0.25
            idx = np.where(proj > cutoff)[0]
            return int(idx[0]), int(idx[-1]) if len(idx) else (0, len(proj))

        l_inner, r_inner = border_span(col_proj)
        t_inner, b_inner = border_span(row_proj)

        l_border = l_inner
        r_border = w - r_inner
        t_border = t_inner
        b_border = h - b_inner

        def ratio(a, b):
            return min(a, b) / max(a, b) if max(a, b) > 0 else 1.0

        h_ratio = ratio(l_border, r_border)
        v_ratio = ratio(t_border, b_border)
        center_score = (h_ratio + v_ratio) / 2 * 100

        defects = []
        if center_score < 65:
            severity = 'severe' if center_score < 45 else 'moderate' if center_score < 55 else 'minor'
            defects.append({
                'type': 'off_centering',
                'location': f'h:{h_ratio:.2f} v:{v_ratio:.2f}',
                'severity': severity,
                'metric': round(center_score, 1),
            })

        return defects, float(center_score)

    # ------------------------------------------------------------------ #
    #  Main inspection                                                     #
    # ------------------------------------------------------------------ #

    def inspect(self, img: np.ndarray) -> Dict:
        """Inspect a card image and return grade, score, and defects."""
        if img is None or img.size == 0:
            return {'grade': 'Unknown', 'score': 0.0,
                    'defects': [], 'centering_score': 0.0}

        cropped = self._detect_card_region(img)
        defects: List[Dict] = []

        defects.extend(self._detect_corner_damage(cropped))
        defects.extend(self._detect_edge_wear(cropped))
        defects.extend(self._detect_surface_defects(cropped))
        centering_defects, center_score = self._detect_centering(cropped)
        defects.extend(centering_defects)

        # Score calculation
        # Penalties calibrated so a card with minor wear on 2 corners
        # still grades Near Mint (75+)
        penalty_map = {'minor': 2, 'moderate': 6, 'severe': 14}
        score = 100.0
        for d in defects:
            score -= penalty_map.get(d.get('severity', 'minor'), 2)

        # Centering penalty: max 8 points (doesn't destroy the grade on its own)
        centering_penalty = min(8.0, (100.0 - center_score) * 0.10)
        score -= centering_penalty
        score = max(0.0, min(100.0, score))

        grade = 'Poor'
        for g, (lo, hi) in self.GRADES.items():
            if lo <= score <= hi:
                grade = g
                break

        return {
            'grade': grade,
            'score': round(score, 1),
            'defects': defects,
            'centering_score': round(center_score, 1),
        }

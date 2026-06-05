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
        gray_full = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY) if len(img.shape) == 3 else img
        tip = max(6, min(h, w) // 20)   # ~50-70px at 400 DPI

        # Border baseline: how white is the *undamaged* border? Sample the
        # mid-points of each edge (away from corners). A white-bordered card
        # has a high baseline, so a white corner is NOT a defect; only a corner
        # that is whiter than this baseline indicates real wear.
        baseline = self._border_white_baseline(gray_full, tip)

        corners = {
            'top_left':     gray_full[0:tip, 0:tip],
            'top_right':    gray_full[0:tip, max(0, w - tip):w],
            'bottom_left':  gray_full[max(0, h - tip):h, 0:tip],
            'bottom_right': gray_full[max(0, h - tip):h, max(0, w - tip):w],
        }

        defects = []
        for name, region in corners.items():
            if region.size == 0:
                continue

            white_ratio = np.sum(region > 230) / region.size
            # Excess whiteness vs the pristine border (negative ⇒ not damaged)
            excess = white_ratio - baseline

            if excess > 0.35:
                severity = 'severe' if excess > 0.55 else 'moderate'
                defects.append({
                    'type': 'corner_whitening', 'location': name,
                    'severity': severity, 'metric': round(float(excess), 3),
                })
            elif excess > 0.22:
                defects.append({
                    'type': 'corner_whitening', 'location': name,
                    'severity': 'minor', 'metric': round(float(excess), 3),
                })

            # Fraying = high-frequency roughness at the tip (rounded/chewed corner)
            edge_density = np.sum(cv2.Canny(region, 40, 120) > 0) / max(region.size, 1)
            if edge_density > 0.55:
                defects.append({
                    'type': 'corner_fraying', 'location': name,
                    'severity': 'moderate' if edge_density > 0.70 else 'minor',
                    'metric': round(float(edge_density), 3),
                })

        return defects

    def _border_white_baseline(self, gray: np.ndarray, tip: int) -> float:
        """Median white-ratio of the four edge mid-sections (the pristine border)."""
        h, w = gray.shape[:2]
        t = max(4, min(h, w) // 50)
        mids = [
            gray[0:t, w // 4: 3 * w // 4],          # top mid
            gray[h - t:h, w // 4: 3 * w // 4],      # bottom mid
            gray[h // 4: 3 * h // 4, 0:t],          # left mid
            gray[h // 4: 3 * h // 4, w - t:w],      # right mid
        ]
        ratios = [np.sum(m > 230) / m.size for m in mids if m.size > 0]
        return float(np.median(ratios)) if ratios else 0.0

    # ------------------------------------------------------------------ #
    #  Edge analysis                                                       #
    # ------------------------------------------------------------------ #

    def _detect_edge_wear(self, img: np.ndarray) -> List[Dict]:
        """
        Detect edge whitening by comparing the extreme edge strip to a strip
        just inside it. Real edge wear makes the very edge whiter than the
        material right behind it. On a white-bordered card both strips are
        white (≈equal) → no false positive.
        """
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY) if len(img.shape) == 3 else img
        h, w = gray.shape
        t = max(3, min(h, w) // 60)   # edge strip thickness

        # (edge strip, reference strip just inside it)
        regions = {
            'top':    (gray[0:t, :],                gray[t:2 * t, :]),
            'bottom': (gray[h - t:h, :],            gray[h - 2 * t:h - t, :]),
            'left':   (gray[:, 0:t],                gray[:, t:2 * t]),
            'right':  (gray[:, w - t:w],            gray[:, w - 2 * t:w - t]),
        }

        defects = []
        for name, (edge, ref) in regions.items():
            if edge.size == 0 or ref.size == 0:
                continue
            edge_white = np.sum(edge > 230) / edge.size
            ref_white  = np.sum(ref  > 230) / ref.size
            excess = edge_white - ref_white

            if excess > 0.30:
                severity = 'severe' if excess > 0.50 else 'moderate'
                defects.append({
                    'type': 'edge_whitening', 'location': name,
                    'severity': severity, 'metric': round(float(excess), 3),
                })
            elif excess > 0.18:
                defects.append({
                    'type': 'edge_whitening', 'location': name,
                    'severity': 'minor', 'metric': round(float(excess), 3),
                })

        return defects

    # ------------------------------------------------------------------ #
    #  Surface analysis                                                    #
    # ------------------------------------------------------------------ #

    def _detect_surface_defects(self, img: np.ndarray) -> List[Dict]:
        """Detect creases/scratches and localized staining (conservative)."""
        defects = []
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY) if len(img.shape) == 3 else img
        h, w = gray.shape

        # Inset 22% on each side — keeps the analysis well clear of the card's
        # printed frame/border lines that previously triggered false creases.
        inset_x = max(15, int(w * 0.22))
        inset_y = max(15, int(h * 0.22))
        center = gray[inset_y:h - inset_y, inset_x:w - inset_x]
        if center.size == 0 or min(center.shape[:2]) < 40:
            return defects

        min_dim = min(center.shape[:2])
        edges = cv2.Canny(center, 60, 180)
        lines = cv2.HoughLinesP(
            edges, 1, np.pi / 180,
            threshold=90,
            minLineLength=int(min_dim * 0.55),   # a crease spans most of the face
            maxLineGap=8,
        )
        if lines is not None:
            # A real crease is a long, near-perfectly straight line. Photo content
            # (bats, shoulders, text) rarely produces multiple such lines.
            long_lines = [
                l for l in lines
                if np.hypot(l[0][2] - l[0][0], l[0][3] - l[0][1]) > min_dim * 0.7
            ]
            if len(long_lines) >= 3:   # require several (was 2) to flag
                defects.append({
                    'type': 'surface_crease', 'location': 'center',
                    'severity': 'severe' if len(long_lines) > 6 else 'moderate',
                    'metric': len(long_lines),
                })

        # Staining — only flag a LOCALIZED abnormally-dark blob, not overall dark
        # photo content. Compare the darkest local region to the median brightness.
        if len(img.shape) == 3:
            small = cv2.resize(center, (64, 64), interpolation=cv2.INTER_AREA)
            blurred = cv2.GaussianBlur(small, (0, 0), sigmaX=3)
            med = float(np.median(blurred))
            darkest = float(np.min(blurred))
            # Stain = a soft dark patch much darker than the typical surface,
            # but not pure black (which would be photo shadow/ink).
            if med > 60 and 20 < darkest < med - 70:
                very_dark = np.sum(blurred < (med - 70)) / blurred.size
                if 0.02 < very_dark < 0.25:   # localized, not the whole image
                    defects.append({
                        'type': 'surface_staining', 'location': 'center',
                        'severity': 'minor', 'metric': round(very_dark, 3),
                    })

        return defects

    # ------------------------------------------------------------------ #
    #  Centering                                                           #
    # ------------------------------------------------------------------ #

    def _detect_centering(self, img: np.ndarray) -> Tuple[List[Dict], float]:
        """
        Measure border symmetry. Returns (defects, score).

        If a clear white border can't be measured on all four sides (e.g. a
        full-bleed card, or detection failed), centering is treated as
        UNMEASURABLE — score 100, no penalty — instead of the old behaviour
        that reported 'off_centering @ h:0.00 v:0.00' as a severe defect.
        """
        h, w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY) if len(img.shape) == 3 else img

        _, thresh = cv2.threshold(gray, 220, 255, cv2.THRESH_BINARY_INV)
        col_proj = np.sum(thresh, axis=0).astype(float)
        row_proj = np.sum(thresh, axis=1).astype(float)

        def border_span(proj):
            mx = proj.max()
            if mx < 1:
                return None
            cutoff = mx * 0.25
            idx = np.where(proj > cutoff)[0]
            if len(idx) == 0:
                return None
            return int(idx[0]), int(idx[-1])

        col = border_span(col_proj)
        row = border_span(row_proj)
        if col is None or row is None:
            return [], 100.0

        l_border, r_border = col[0], w - col[1]
        t_border, b_border = row[0], h - row[1]

        # Borders must be real but reasonable (1%–35% of the dimension). Outside
        # that range the measurement isn't trustworthy → treat as unmeasurable.
        def plausible(a, b, dim):
            lo, hi = dim * 0.01, dim * 0.35
            return lo <= a <= hi and lo <= b <= hi

        if not (plausible(l_border, r_border, w) and plausible(t_border, b_border, h)):
            return [], 100.0

        def ratio(a, b):
            return min(a, b) / max(a, b) if max(a, b) > 0 else 1.0

        h_ratio = ratio(l_border, r_border)
        v_ratio = ratio(t_border, b_border)
        center_score = (h_ratio + v_ratio) / 2 * 100

        defects = []
        if center_score < 60:
            severity = 'severe' if center_score < 40 else 'moderate' if center_score < 52 else 'minor'
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

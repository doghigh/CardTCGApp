import cv2
import numpy as np
from typing import List, Dict, Tuple


class CardInspector:
    """Computer vision based card condition grading."""

    GRADES = {
        'Gem Mint': (95, 100),
        'Mint': (90, 94),
        'Near Mint': (80, 89),
        'Excellent': (70, 79),
        'Very Good': (60, 69),
        'Good': (50, 59),
        'Played': (35, 49),
        'Poor': (0, 34),
    }

    def _detect_card_region(self, img: np.ndarray) -> np.ndarray:
        """Crop to the main card area using contour detection."""
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY) if len(img.shape) == 3 else img
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            return img

        largest = max(contours, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(largest)

        if w < 50 or h < 50:
            return img

        return img[y:y + h, x:x + w]

    def _detect_corner_damage(self, img: np.ndarray) -> List[Dict]:
        """Detect whitening and fraying in corners."""
        h, w = img.shape[:2]
        corner_size = max(10, min(h, w) // 8)
        corners = {
            'top_left': img[0:corner_size, 0:corner_size],
            'top_right': img[0:corner_size, max(0, w - corner_size):w],
            'bottom_left': img[max(0, h - corner_size):h, 0:corner_size],
            'bottom_right': img[max(0, h - corner_size):h, max(0, w - corner_size):w],
        }

        defects = []
        for name, region in corners.items():
            if region.size == 0:
                continue
            gray = cv2.cvtColor(region, cv2.COLOR_RGB2GRAY) if len(region.shape) == 3 else region
            white_ratio = np.sum(gray > 230) / gray.size
            edges = cv2.Canny(gray, 50, 150)
            edge_density = np.sum(edges > 0) / edges.size

            if white_ratio > 0.35:
                severity = 'severe' if white_ratio > 0.6 else 'moderate' if white_ratio > 0.45 else 'minor'
                defects.append({
                    'type': 'corner_whitening',
                    'location': name,
                    'severity': severity,
                    'metric': round(float(white_ratio), 3),
                })
            if edge_density > 0.25:
                defects.append({
                    'type': 'corner_fraying',
                    'location': name,
                    'severity': 'moderate' if edge_density > 0.4 else 'minor',
                    'metric': round(float(edge_density), 3),
                })
        return defects

    def _detect_edge_wear(self, img: np.ndarray) -> List[Dict]:
        """Detect edge whitening."""
        h, w = img.shape[:2]
        edge_thickness = max(3, min(h, w) // 60)
        regions = {
            'top': img[0:edge_thickness, :],
            'bottom': img[max(0, h - edge_thickness):h, :],
            'left': img[:, 0:edge_thickness],
            'right': img[:, max(0, w - edge_thickness):w],
        }

        defects = []
        for name, region in regions.items():
            if region.size == 0:
                continue
            gray = cv2.cvtColor(region, cv2.COLOR_RGB2GRAY) if len(region.shape) == 3 else region
            white_ratio = np.sum(gray > 230) / gray.size
            if white_ratio > 0.30:
                severity = 'severe' if white_ratio > 0.55 else 'moderate' if white_ratio > 0.40 else 'minor'
                defects.append({
                    'type': 'edge_whitening',
                    'location': name,
                    'severity': severity,
                    'metric': round(float(white_ratio), 3),
                })
        return defects

    def _detect_surface_defects(self, img: np.ndarray) -> List[Dict]:
        """Detect creases, scratches, stains, and sharpness."""
        defects = []
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY) if len(img.shape) == 3 else img
        h, w = gray.shape

        # Surface creases / scratches
        crop = max(10, min(h, w) // 20)
        center = gray[crop:h - crop, crop:w - crop]
        edges = cv2.Canny(center, 60, 180)
        lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=80,
                                minLineLength=min(h, w) // 4, maxLineGap=10)

        if lines is not None and len(lines) > 0:
            long_lines = [l for l in lines if np.hypot(l[0][2] - l[0][0], l[0][3] - l[0][1]) > min(h, w) // 3]
            if long_lines:
                severity = 'severe' if len(long_lines) > 3 else 'moderate' if len(long_lines) > 1 else 'minor'
                defects.append({
                    'type': 'surface_crease_or_scratch',
                    'location': 'center',
                    'severity': severity,
                    'metric': len(long_lines),
                })

        # Staining / discoloration
        if len(img.shape) == 3:
            hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV)
            val = hsv[:, :, 2]
            dark_anomaly = np.sum(val < 60) / val.size
            if dark_anomaly > 0.08:
                defects.append({
                    'type': 'surface_staining',
                    'location': 'center',
                    'severity': 'moderate' if dark_anomaly > 0.15 else 'minor',
                    'metric': round(float(dark_anomaly), 3),
                })

        # Sharpness
        lap_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        if lap_var < 50:
            defects.append({
                'type': 'low_sharpness',
                'location': 'overall',
                'severity': 'minor',
                'metric': round(float(lap_var), 2),
            })

        return defects

    def _detect_centering(self, img: np.ndarray) -> Tuple[List[Dict], float]:
        """Calculate centering score."""
        h, w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY) if len(img.shape) == 3 else img
        _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)

        col_sum = np.sum(thresh, axis=0)
        row_sum = np.sum(thresh, axis=1)

        def find_inner(arr):
            mx = arr.max() if arr.max() > 0 else 1
            idx = np.where(arr > mx * 0.3)[0]
            if len(idx) == 0:
                return 0, len(arr)
            return int(idx[0]), int(idx[-1])

        left, right = find_inner(col_sum)
        top, bottom = find_inner(row_sum)

        lb, rb = left, w - right
        tb, bb = top, h - bottom

        def ratio(a, b):
            return min(a, b) / max(a, b) if max(a, b) > 0 else 1.0

        h_c = ratio(lb, rb)
        v_c = ratio(tb, bb)
        score = (h_c + v_c) / 2 * 100

        defects = []
        if score < 70:
            severity = 'severe' if score < 50 else 'moderate' if score < 60 else 'minor'
            defects.append({
                'type': 'off_centering',
                'location': f'h:{h_c:.2f}/v:{v_c:.2f}',
                'severity': severity,
                'metric': round(float(score), 1),
            })

        return defects, float(score)

    def inspect(self, img: np.ndarray) -> Dict:
        """Main inspection method - returns grade, score, and defects."""
        if img is None or img.size == 0:
            return {
                'grade': 'Unknown',
                'score': 0.0,
                'defects': [],
                'centering_score': 0.0
            }

        cropped = self._detect_card_region(img)
        defects = []

        defects.extend(self._detect_corner_damage(cropped))
        defects.extend(self._detect_edge_wear(cropped))
        defects.extend(self._detect_surface_defects(cropped))

        cd, cs = self._detect_centering(cropped)
        defects.extend(cd)

        # Calculate final score
        score = 100.0
        penalty = {'minor': 3, 'moderate': 8, 'severe': 18}
        for d in defects:
            score -= penalty.get(d.get('severity', 'minor'), 3)

        score -= (100 - cs) * 0.15
        score = max(0, min(100, score))

        # Determine grade
        grade = 'Poor'
        for g, (lo, hi) in self.GRADES.items():
            if lo <= score <= hi:
                grade = g
                break

        return {
            'grade': grade,
            'score': round(score, 1),
            'defects': defects,
            'centering_score': round(cs, 1),
        }
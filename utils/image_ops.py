"""
Shared image operations — rotation and skew correction for card scans.
"""

import logging
import cv2
import numpy as np
from typing import Optional

logger = logging.getLogger(__name__)


def rotate_90_cw(img: np.ndarray) -> np.ndarray:
    """Rotate image 90° clockwise."""
    return cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)


def rotate_90_ccw(img: np.ndarray) -> np.ndarray:
    """Rotate image 90° counter-clockwise."""
    return cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)


def rotate_180(img: np.ndarray) -> np.ndarray:
    """Rotate image 180°."""
    return cv2.rotate(img, cv2.ROTATE_180)


def deskew(img: np.ndarray, max_angle: float = 15.0) -> np.ndarray:
    """
    Auto-correct small skew/tilt in a scanned card.

    Detects the dominant edge angle of the card against its background and
    rotates the image to make those edges horizontal/vertical. Only corrects
    angles within ±max_angle degrees (avoids flipping a 90°-rotated card).

    Returns the deskewed image, or the original if no reliable angle is found.
    """
    if img is None or img.size == 0:
        return img

    try:
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY) if len(img.shape) == 3 else img

        # Angle detection is the expensive part (threshold + findNonZero +
        # minAreaRect). On a 600-DPI scan that's millions of points, so detect
        # the skew on a downscaled copy — the angle is unchanged by scaling, and
        # we only warp the full-resolution image if a correction is actually
        # needed. This keeps batch imports fast.
        h, w = gray.shape[:2]
        scale = 1000.0 / max(h, w)
        small = (cv2.resize(gray, None, fx=scale, fy=scale,
                            interpolation=cv2.INTER_AREA)
                 if scale < 1.0 else gray)

        blurred = cv2.GaussianBlur(small, (5, 5), 0)
        _, thresh = cv2.threshold(blurred, 0, 255,
                                  cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # If the card is darker than background this gives card=white; if not,
        # invert so the card region is the foreground.
        if np.mean(thresh) > 127:
            thresh = cv2.bitwise_not(thresh)

        coords = cv2.findNonZero(thresh)
        if coords is None or len(coords) < 50:
            return img

        # minAreaRect gives the tilt of the smallest rotated bounding box
        angle = cv2.minAreaRect(coords)[-1]

        # Normalise OpenCV's angle convention to [-45, 45]
        if angle < -45:
            angle = 90 + angle
        elif angle > 45:
            angle = angle - 90

        # Ignore tiny noise and large angles (likely a 90° rotation, not skew).
        # Early-out here means no warpAffine runs on already-straight scans.
        if abs(angle) < 0.3 or abs(angle) > max_angle:
            return img

        return _rotate_bound(img, angle)

    except Exception as exc:
        logger.debug("Deskew error: %s", exc)
        return img


def _rotate_bound(img: np.ndarray, angle: float) -> np.ndarray:
    """Rotate by an arbitrary angle, expanding the canvas so nothing is clipped."""
    h, w = img.shape[:2]
    cx, cy = w / 2.0, h / 2.0

    matrix = cv2.getRotationMatrix2D((cx, cy), angle, 1.0)
    cos = abs(matrix[0, 0])
    sin = abs(matrix[0, 1])

    new_w = int((h * sin) + (w * cos))
    new_h = int((h * cos) + (w * sin))

    matrix[0, 2] += (new_w / 2.0) - cx
    matrix[1, 2] += (new_h / 2.0) - cy

    border = (255, 255, 255) if len(img.shape) == 3 else 255
    return cv2.warpAffine(
        img, matrix, (new_w, new_h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=border,
    )

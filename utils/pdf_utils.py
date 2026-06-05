"""
PDF helpers for card import — render pages to images via pypdfium2.

pypdfium2 is used (not PyMuPDF) because its Apache/BSD license is safe for
commercial distribution and it bundles its own renderer (no external binaries
to package for the Microsoft Store).
"""

import logging
from pathlib import Path
from typing import List, Tuple, Optional

import numpy as np

logger = logging.getLogger(__name__)

try:
    import pypdfium2 as pdfium
    HAS_PDFIUM = True
except ImportError:
    HAS_PDFIUM = False


def is_pdf(path) -> bool:
    return str(path).lower().endswith(".pdf")


def page_count(path) -> int:
    if not HAS_PDFIUM:
        return 0
    try:
        pdf = pdfium.PdfDocument(str(path))
        n = len(pdf)
        pdf.close()
        return n
    except Exception as exc:
        logger.warning("Could not read PDF %s: %s", path, exc)
        return 0


def page_sizes(path) -> List[Tuple[float, float]]:
    """Return (width, height) in points for each page — cheap, no rendering."""
    if not HAS_PDFIUM:
        return []
    try:
        pdf = pdfium.PdfDocument(str(path))
        sizes = [tuple(pdf[i].get_size()) for i in range(len(pdf))]
        pdf.close()
        return sizes
    except Exception as exc:
        logger.warning("Could not size PDF %s: %s", path, exc)
        return []


def render_page(path, index: int = 0, dpi: int = 300) -> Optional[np.ndarray]:
    """Render one PDF page to an RGB numpy array, or None on failure."""
    if not HAS_PDFIUM:
        return None
    try:
        pdf = pdfium.PdfDocument(str(path))
        page = pdf[index]
        bitmap = page.render(scale=dpi / 72.0)
        pil = bitmap.to_pil().convert("RGB")
        arr = np.asarray(pil)
        pdf.close()
        return arr
    except Exception as exc:
        logger.warning("Could not render PDF %s p%d: %s", path, index, exc)
        return None

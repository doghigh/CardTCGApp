import cv2
import numpy as np
from PIL import Image
import io
import time
import logging
from pathlib import Path
from typing import Optional, List

try:
    import twain
    HAS_TWAIN = True
except ImportError:
    HAS_TWAIN = False

logger = logging.getLogger(__name__)


class ScannerInterface:
    def __init__(self):
        self._cancel_requested = False

    def cancel(self):
        self._cancel_requested = True

    def list_sources(self) -> List[str]:
        if not HAS_TWAIN:
            return []
        try:
            sm = twain.SourceManager(0)
            sources = sm.GetSourceList()
            sm.destroy()
            return list(sources)
        except Exception as e:
            logger.warning("List sources error: %s", e)
            return []

    def _enhance_image(self, img: np.ndarray) -> np.ndarray:
        """
        Gently clean up a scan.

        Correct order matters: DENOISE first, then a mild sharpen. The previous
        version sharpened with a harsh kernel (center=9) and ran CLAHE *before*
        denoising, which amplified sensor noise into the heavy grain you saw.
        """
        if img is None or img.size == 0:
            return img

        try:
            # 1) Edge-preserving denoise. Bilateral keeps fine text/edges sharp
            #    while smoothing flat noise — fastNlMeans was over-smoothing text.
            denoised = cv2.bilateralFilter(
                img, d=5,
                sigmaColor=40,   # how much color difference is "noise"
                sigmaSpace=40,   # spatial reach
            )

            # 2) Subtle unsharp mask for crispness (low amount → no halos/grain)
            blur = cv2.GaussianBlur(denoised, (0, 0), sigmaX=1.5)
            amount = 0.4
            enhanced = cv2.addWeighted(denoised, 1 + amount, blur, -amount, 0)

            return enhanced

        except Exception as e:
            logger.warning("Enhancement skipped: %s", e)
            return img

    def scan(self, source_name: Optional[str] = None, dpi: int = 400, duplex: bool = False) -> List[np.ndarray]:
        if not HAS_TWAIN:
            return []

        images: List[np.ndarray] = []

        try:
            sm = twain.SourceManager(0)
            src = sm.OpenSource(source_name) if source_name else sm.OpenSource()
            if not src:
                sm.destroy()
                return []

            logger.info("Opened scanner: %s @ %d DPI", source_name, dpi)

            # Higher quality settings
            try:
                src.SetCapability(twain.ICAP_XRESOLUTION, twain.TWTY_FIX32, float(dpi))
                src.SetCapability(twain.ICAP_YRESOLUTION, twain.TWTY_FIX32, float(dpi))
                src.SetCapability(twain.ICAP_PIXELTYPE, twain.TWTY_UINT16, twain.TWPT_RGB)
                src.SetCapability(twain.ICAP_BITDEPTH, twain.TWTY_UINT16, 24)  # 24-bit color
            except Exception as e:
                logger.debug("Capability setting warning: %s", e)

            # Disable in-transfer compression — JPEG compression is a major
            # source of the blocky color artifacts/grain on card scans.
            try:
                src.SetCapability(twain.ICAP_COMPRESSION, twain.TWTY_UINT16, twain.TWCP_NONE)
            except Exception as e:
                logger.debug("Compression setting skipped: %s", e)

            # Ask the scanner NOT to apply its own auto image processing where
            # the driver exposes it (keeps the capture faithful/sharp).
            for cap_name, value in (
                ("ICAP_AUTODISCARDBLANKPAGES", None),   # leave blanks (we handle)
                ("ICAP_NOISEFILTER", "TWNF_NONE"),      # no driver noise filter
            ):
                try:
                    cap = getattr(twain, cap_name, None)
                    val = getattr(twain, value) if isinstance(value, str) else value
                    if cap is not None and val is not None:
                        src.SetCapability(cap, twain.TWTY_UINT16, val)
                except Exception:
                    pass

            if duplex:
                try:
                    src.SetCapability(twain.CAP_FEEDERENABLED, twain.TWTY_BOOL, True)
                    src.SetCapability(twain.CAP_DUPLEXENABLED, twain.TWTY_BOOL, True)
                    logger.info("Duplex + feeder enabled")
                except (AttributeError, Exception) as e:
                    logger.debug("Duplex not available: %s", e)

            self._cancel_requested = False
            src.RequestAcquire(0, 0)

            while not self._cancel_requested:
                try:
                    rv = src.XferImageNatively()
                    if not rv:
                        break
                    handle = rv[0] if isinstance(rv, (tuple, list)) else rv

                    bmp_bytes = twain.DIBToBMFile(handle)
                    img_pil = Image.open(io.BytesIO(bmp_bytes))
                    arr = np.array(img_pil.convert('RGB'))

                    arr = self._enhance_image(arr)
                    images.append(arr)

                except twain.exceptions.SequenceError:
                    break
                except Exception as e:
                    logger.warning("Transfer error: %s", e)
                    break

                time.sleep(0.1)

            if self._cancel_requested:
                logger.info("Scan cancelled by user")

            src.destroy()
            sm.destroy()

            logger.info("Finished scanning — %d image(s)", len(images))
            return images

        except Exception as e:
            logger.error("Scan error: %s", e)
            return []

    def scan_from_file(self, path: str) -> Optional[np.ndarray]:
        try:
            img = cv2.imread(path)
            if img is None:
                pil = Image.open(path).convert('RGB')
                arr = np.array(pil)
            else:
                arr = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            return arr
        except Exception as e:
            logger.warning("File load error: %s", e)
            return None
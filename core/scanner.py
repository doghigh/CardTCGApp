import cv2
import numpy as np
from PIL import Image
import io
from pathlib import Path
from typing import Optional, List, Tuple

try:
    import twain
    HAS_TWAIN = True
except ImportError:
    HAS_TWAIN = False

try:
    import pytesseract
    HAS_TESSERACT = True
except ImportError:
    HAS_TESSERACT = False


class ScannerInterface:
    """Handles TWAIN scanning (including duplex), file loading, and auto-rotation."""

    def list_sources(self) -> List[str]:
        """List all available TWAIN scanner sources."""
        if not HAS_TWAIN:
            return []
        try:
            sm = twain.SourceManager(0)
            sources = sm.GetSourceList()
            sm.destroy()
            return list(sources)
        except Exception:
            return []

    def _auto_rotate(self, img: np.ndarray) -> np.ndarray:
        """Automatically correct 180° rotation using Tesseract OSD + fallback."""
        if img is None or img.size == 0:
            return img

        try:
            gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY) if len(img.shape) == 3 else img

            # Tesseract OSD (most accurate)
            if HAS_TESSERACT:
                try:
                    osd = pytesseract.image_to_osd(gray, output_type=pytesseract.Output.DICT)
                    angle = int(osd.get('rotate', 0))
                    if angle in (90, 180, 270, -90, -180, -270):
                        if angle in (90, -270):
                            return cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
                        elif angle in (180, -180):
                            return cv2.rotate(img, cv2.ROTATE_180)
                        elif angle in (270, -90):
                            return cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
                except:
                    pass

            # Fallback: text density (more content at bottom = likely upside down)
            h, w = gray.shape
            top = np.mean(gray[0:h//4, :])
            bottom = np.mean(gray[3*h//4:, :])

            if bottom > top * 1.25:
                return cv2.rotate(img, cv2.ROTATE_180)

        except Exception:
            pass

        return img

    def scan(self, source_name: Optional[str] = None, dpi: int = 300, duplex: bool = False) -> List[np.ndarray]:
        """
        Scan from TWAIN device.
        Returns a list of images (1 image for normal scan, 2 for duplex).
        """
        if not HAS_TWAIN:
            return []

        images: List[np.ndarray] = []

        try:
            sm = twain.SourceManager(0)
            src = sm.OpenSource(source_name) if source_name else sm.OpenSource()
            if not src:
                sm.destroy()
                return []

            # Basic settings
            try:
                src.SetCapability(twain.ICAP_XRESOLUTION, twain.TWTY_FIX32, float(dpi))
                src.SetCapability(twain.ICAP_YRESOLUTION, twain.TWTY_FIX32, float(dpi))
                src.SetCapability(twain.ICAP_PIXELTYPE, twain.TWTY_UINT16, twain.TWPT_RGB)
            except Exception:
                pass

            # === DUPLEX SUPPORT ===
            if duplex:
                try:
                    # Enable duplex if the scanner supports it
                    if src.GetCapability(twain.CAP_DUPLEX, twain.TWON_DONTCARE16) is not None:
                        src.SetCapability(twain.CAP_DUPLEXENABLED, twain.TWTY_BOOL, True)
                        print("✅ Duplex mode enabled on scanner")
                except Exception as e:
                    print(f"⚠️ Duplex not supported by scanner: {e}")

            # Start acquisition
            src.RequestAcquire(0, 0)

            # Handle one or more images (duplex returns two)
            while True:
                handle = src.XferImageNatively()
                if not handle:
                    break

                try:
                    bmp_bytes = twain.DIBToBMFile(handle[0])
                    img = Image.open(io.BytesIO(bmp_bytes))
                    arr = np.array(img.convert('RGB'))
                    arr = self._auto_rotate(arr)
                    images.append(arr)
                except Exception as e:
                    print(f"Image conversion error: {e}")

            src.destroy()
            sm.destroy()

            if not images:
                print("⚠️ No images received from scanner")
            elif duplex and len(images) == 1:
                print("⚠️ Duplex requested but only one side received")

            return images

        except Exception as e:
            print(f"Scan error: {e}")
            return []

    def scan_from_file(self, path: str) -> Optional[np.ndarray]:
        """Load image from disk with auto-rotation."""
        try:
            img = cv2.imread(path)
            if img is None:
                pil = Image.open(path).convert('RGB')
                arr = np.array(pil)
            else:
                arr = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

            return self._auto_rotate(arr)
        except Exception as e:
            print(f"File load error: {e}")
            return None
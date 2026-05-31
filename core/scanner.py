import cv2
import numpy as np
from PIL import Image
import io
import time
from pathlib import Path
from typing import Optional, List

try:
    import twain
    HAS_TWAIN = True
except ImportError:
    HAS_TWAIN = False


class ScannerInterface:
    def list_sources(self) -> List[str]:
        if not HAS_TWAIN:
            return []
        try:
            sm = twain.SourceManager(0)
            sources = sm.GetSourceList()
            sm.destroy()
            return list(sources)
        except Exception as e:
            print(f"List sources error: {e}")
            return []

    def _enhance_image(self, img: np.ndarray) -> np.ndarray:
        """Post-process scan for better card quality."""
        if img is None or img.size == 0:
            return img

        try:
            # Convert to float for better math
            img_float = img.astype(np.float32) / 255.0

            # Sharpen
            kernel = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]])
            sharpened = cv2.filter2D(img, -1, kernel)

            # Increase contrast + slight saturation
            lab = cv2.cvtColor(sharpened, cv2.COLOR_RGB2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8,8))
            l = clahe.apply(l)
            enhanced = cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2RGB)

            # Light noise reduction
            enhanced = cv2.fastNlMeansDenoisingColored(enhanced, None, 10, 10, 7, 21)

            print("✅ Image enhancement applied (sharpen + contrast)")
            return enhanced

        except Exception as e:
            print(f"Enhancement skipped: {e}")
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

            print(f"✅ Opened scanner: {source_name} @ {dpi} DPI")

            # Higher quality settings
            try:
                src.SetCapability(twain.ICAP_XRESOLUTION, twain.TWTY_FIX32, float(dpi))
                src.SetCapability(twain.ICAP_YRESOLUTION, twain.TWTY_FIX32, float(dpi))
                src.SetCapability(twain.ICAP_PIXELTYPE, twain.TWTY_UINT16, twain.TWPT_RGB)
                src.SetCapability(twain.ICAP_BITDEPTH, twain.TWTY_UINT16, 24)  # 24-bit color
            except Exception as e:
                print(f"Setting warning: {e}")

            if duplex:
                try:
                    src.SetCapability(twain.CAP_FEEDERENABLED, twain.TWTY_BOOL, True)
                    src.SetCapability(twain.CAP_DUPLEXENABLED, twain.TWTY_BOOL, True)
                    print("✅ Duplex + Feeder enabled")
                except (AttributeError, Exception) as e:
                    print(f"Duplex not available: {e}")

            src.RequestAcquire(0, 0)

            while True:
                try:
                    rv = src.XferImageNatively()
                    if not rv:
                        break
                    handle = rv[0] if isinstance(rv, (tuple, list)) else rv

                    bmp_bytes = twain.DIBToBMFile(handle)
                    img_pil = Image.open(io.BytesIO(bmp_bytes))
                    arr = np.array(img_pil.convert('RGB'))

                    # Apply quality enhancement
                    arr = self._enhance_image(arr)
                    images.append(arr)

                except twain.exceptions.SequenceError:
                    break
                except Exception as e:
                    print(f"Transfer error: {e}")
                    break

                time.sleep(0.1)

            src.destroy()
            sm.destroy()

            print(f"✅ Finished scanning — {len(images)} image(s)")
            return images

        except Exception as e:
            print(f"Scan error: {e}")
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
            print(f"File load error: {e}")
            return None
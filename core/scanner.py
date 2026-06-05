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
            print(f"List sources error: {e}")
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
            # 1) Denoise first — removes scanner sensor grain before anything
            #    amplifies it. Moderate strength, edge-preserving.
            denoised = cv2.fastNlMeansDenoisingColored(
                img, None,
                h=7,            # luminance filter strength
                hColor=7,       # colour filter strength
                templateWindowSize=7,
                searchWindowSize=21,
            )

            # 2) Gentle unsharp mask — adds crispness without amplifying noise.
            #    sharpened = img*(1+amount) - blurred*amount
            blur = cv2.GaussianBlur(denoised, (0, 0), sigmaX=3)
            amount = 0.6
            sharpened = cv2.addWeighted(denoised, 1 + amount, blur, -amount, 0)

            # 3) Very mild local contrast (low clip so it doesn't re-introduce noise)
            lab = cv2.cvtColor(sharpened, cv2.COLOR_RGB2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=1.2, tileGridSize=(8, 8))
            l = clahe.apply(l)
            enhanced = cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2RGB)

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
                    print(f"Transfer error: {e}")
                    break

                time.sleep(0.1)

            if self._cancel_requested:
                print("⏹ Scan cancelled by user")

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
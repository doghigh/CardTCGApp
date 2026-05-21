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

try:
    import pytesseract
    HAS_TESSERACT = True
except ImportError:
    HAS_TESSERACT = False


class ScannerInterface:
    """Handles TWAIN scanning with duplex support."""

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

    def scan(self, source_name: Optional[str] = None, dpi: int = 300, duplex: bool = False) -> List[np.ndarray]:
        if not HAS_TWAIN:
            return []

        images: List[np.ndarray] = []

        try:
            sm = twain.SourceManager(0)
            src = sm.OpenSource(source_name) if source_name else sm.OpenSource()
            if not src:
                print("Failed to open source")
                sm.destroy()
                return []

            print(f"✅ Opened scanner: {source_name}")

            # Basic settings
            try:
                src.SetCapability(twain.ICAP_XRESOLUTION, twain.TWTY_FIX32, float(dpi))
                src.SetCapability(twain.ICAP_YRESOLUTION, twain.TWTY_FIX32, float(dpi))
                src.SetCapability(twain.ICAP_PIXELTYPE, twain.TWTY_UINT16, twain.TWPT_RGB)
            except Exception as e:
                print(f"Setting capability warning: {e}")

            if duplex:
                try:
                    src.SetCapability(twain.CAP_FEEDERENABLED, twain.TWTY_BOOL, True)
                    print("✅ Feeder enabled")
                except Exception as e:
                    print(f"Feeder warning: {e}")
                try:
                    src.SetCapability(twain.CAP_DUPLEXENABLED, twain.TWTY_BOOL, True)
                    print("✅ Duplex enabled")
                except Exception as e:
                    print(f"Duplex warning: {e}")

            src.RequestAcquire(0, 0)

            # Transfer loop
            while True:
                try:
                    rv = src.XferImageNatively()
                    if not rv:
                        break

                    handle = rv[0] if isinstance(rv, (tuple, list)) else rv
                    bmp_bytes = twain.DIBToBMFile(handle)
                    img_pil = Image.open(io.BytesIO(bmp_bytes))
                    arr = np.array(img_pil.convert('RGB'))
                    images.append(arr)
                    print(f"✅ Processed image {len(images)} - shape: {arr.shape}")

                except twain.exceptions.SequenceError:
                    print("✅ Transfer sequence completed")
                    break
                except Exception as e:
                    print(f"Transfer error: {e}")
                    break

                time.sleep(0.1)

            src.destroy()
            sm.destroy()

            print(f"✅ Finished scanning — total images: {len(images)}")
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
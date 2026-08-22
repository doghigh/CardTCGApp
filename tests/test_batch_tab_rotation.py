import cv2
import numpy as np

import ui.batch_tab as batch_tab_module
from ui.batch_tab import ImageBatchWorker
from core.database import Database
from core.inspector import CardInspector
from core.scanner import ScannerInterface


class _FakeIdentifier:
    def identify_card(self, front, back):
        return {'name': 'Test Card', 'set_name': None, 'card_number': None,
                'game': 'Other', 'year': None, 'rarity': None,
                'condition': {'score': 85, 'defects': []},
                'front_rotation': 180, 'back_rotation': 0}


class _FakeValuator:
    def value_summary(self, *args, **kwargs):
        return {'estimated': 0.0, 'source': '', 'sample': 0}


def _marked_png(path, h=40, w=20):
    """Write a PNG with a distinct marker in the top-left corner; return the
    in-memory RGB array so the test can assert against the ORIGINAL, not just
    re-derive it from the file it's checking."""
    img = np.full((h, w, 3), 255, np.uint8)
    img[0:5, 0:5] = (10, 20, 30)
    cv2.imwrite(str(path), cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
    return img


def test_saved_file_reflects_front_rotation(tmp_path, monkeypatch):
    """The whole point of this feature: does the correction reach disk?

    front_rotation=180 on a marker whose original position is top-left must
    produce a saved file with the marker at bottom-right — proof this isn't
    just an in-memory transform that gets discarded before cv2.imwrite.
    """
    scans_dir = tmp_path / "scans"
    scans_dir.mkdir()
    monkeypatch.setattr(batch_tab_module, "SCANS_DIR", scans_dir)

    folder = tmp_path / "import"
    folder.mkdir()
    original = _marked_png(folder / "card_1.png")

    worker = ImageBatchWorker(
        folder=folder, db=Database(tmp_path / "t.db"), scanner=ScannerInterface(),
        inspector=CardInspector(), identifier=_FakeIdentifier(),
        valuator=_FakeValuator(), auto_value=False, pairing=ImageBatchWorker.SINGLE,
    )
    worker.run()

    saved = list(scans_dir.glob("*_front.png"))
    assert len(saved) == 1, f"expected exactly one saved front image, found {saved}"
    saved_img = cv2.cvtColor(cv2.imread(str(saved[0])), cv2.COLOR_BGR2RGB)

    assert not np.array_equal(saved_img, original)
    assert np.array_equal(saved_img[-5:, -5:], np.full((5, 5, 3), (10, 20, 30), np.uint8))

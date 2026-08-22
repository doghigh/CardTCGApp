import numpy as np

from ui.scan_tab import ScanTab


class _FakeView:
    """Stands in for ImageViewer — records what it was shown."""

    def __init__(self):
        self.images = []

    def set_image(self, img):
        self.images.append(img)


class _FakeScanTab:
    """Borrows the real method under test; supplies only what it touches."""

    _apply_rotation = ScanTab._apply_rotation

    def __init__(self, front, back):
        self.current_front_img = front
        self.current_back_img = back
        self.front_view = _FakeView()
        self.back_view = _FakeView()
        self._front_rotation_applied = False
        self._back_rotation_applied = False


def _marked(h=40, w=20):
    img = np.full((h, w, 3), 255, np.uint8)
    img[0:5, 0:5] = (10, 20, 30)   # marker in the top-left corner
    return img


def test_no_rotation_leaves_images_untouched():
    front, back = _marked(), _marked()
    tab = _FakeScanTab(front, back)
    tab._apply_rotation({'front_rotation': 0, 'back_rotation': 0})
    assert tab.current_front_img is front
    assert tab.current_back_img is back
    assert tab.front_view.images == []
    assert tab.back_view.images == []


def test_missing_rotation_keys_default_to_no_op():
    """Trial-blocked and OCR-fallback info dicts carry no rotation keys at all."""
    front, back = _marked(), _marked()
    tab = _FakeScanTab(front, back)
    tab._apply_rotation({'name': None})
    assert tab.current_front_img is front
    assert tab.current_back_img is back


def test_front_rotation_applied_and_view_refreshed():
    front = _marked()
    tab = _FakeScanTab(front, None)
    tab._apply_rotation({'front_rotation': 90, 'back_rotation': 0})
    assert tab.current_front_img is not front
    assert np.array_equal(tab.current_front_img[0:5, -5:], np.full((5, 5, 3), (10, 20, 30), np.uint8))
    assert tab.front_view.images == [tab.current_front_img]


def test_back_rotation_applied_independently_of_front():
    back = _marked()
    tab = _FakeScanTab(_marked(), back)
    tab._apply_rotation({'front_rotation': 0, 'back_rotation': 180})
    assert tab.current_back_img is not back
    assert np.array_equal(tab.current_back_img[-5:, -5:], np.full((5, 5, 3), (10, 20, 30), np.uint8))
    assert tab.back_view.images == [tab.current_back_img]


def test_back_rotation_skipped_when_no_back_image():
    tab = _FakeScanTab(_marked(), None)
    tab._apply_rotation({'front_rotation': 0, 'back_rotation': 180})
    assert tab.current_back_img is None
    assert tab.back_view.images == []


def test_second_pass_does_not_reapply_to_an_unchanged_front():
    """Regression for M1: loading front then back must not let the second
    identify pass re-judge (and potentially re-rotate) the already-corrected
    front."""
    front = _marked()
    tab = _FakeScanTab(front, None)

    # Pass 1: front loaded, gets corrected.
    tab._apply_rotation({'front_rotation': 90, 'back_rotation': 0})
    corrected_front = tab.current_front_img
    assert corrected_front is not front
    assert tab.front_view.images == [corrected_front]

    # Pass 2: back has now been loaded too; identify runs again and (this
    # time, plausibly by model variance) says the front needs 180 more.
    # It must NOT be applied — the front was already judged in pass 1.
    # (In the real flow, _load_done('back', ...) resets _back_rotation_applied
    # to False when the back is freshly loaded — simulate that side effect
    # here since we're calling _apply_rotation directly.)
    tab.current_back_img = _marked()
    tab._back_rotation_applied = False
    tab._apply_rotation({'front_rotation': 180, 'back_rotation': 90})

    assert tab.current_front_img is corrected_front   # untouched by pass 2
    assert tab.front_view.images == [corrected_front]  # no second repaint
    # Back, being freshly present, is still eligible and gets corrected:
    assert tab.current_back_img is not None
    assert tab.back_view.images == [tab.current_back_img]


def test_reloading_a_side_resets_its_flag():
    """A genuinely new image on a side must be eligible for correction again,
    even after that side was already judged once."""
    tab = _FakeScanTab(_marked(), None)
    tab._apply_rotation({'front_rotation': 90, 'back_rotation': 0})
    assert tab._front_rotation_applied is True

    # Simulate _load_done('front', ...) loading a NEW front image: the real
    # method resets the flag before this test's direct field assignment.
    tab.current_front_img = _marked()
    tab._front_rotation_applied = False

    tab._apply_rotation({'front_rotation': 180, 'back_rotation': 0})
    assert tab.front_view.images[-1] is tab.current_front_img
    assert np.array_equal(tab.current_front_img[-5:, -5:], np.full((5, 5, 3), (10, 20, 30), np.uint8))

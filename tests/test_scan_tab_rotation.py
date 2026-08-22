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

import numpy as np

from ui.batch_review_dialog import BatchProcessWorker
from core.inspector import CardInspector


class _FakeIdentifier:
    def __init__(self, front_rotation=0, back_rotation=0):
        self._front_rotation = front_rotation
        self._back_rotation = back_rotation

    def identify_card(self, front, back):
        return {'name': 'Test Card', 'set_name': None, 'card_number': None,
                'game': 'Magic: The Gathering', 'year': None, 'rarity': None,
                'condition': {'score': 85, 'defects': []},
                'front_rotation': self._front_rotation,
                'back_rotation': self._back_rotation}


class _FakeValuator:
    """A real CardValuator would make a live Scryfall/eBay network call here —
    this test is about rotation wiring, not valuation, so stub it out."""

    def value_summary(self, *args, **kwargs):
        return {'estimated': 0.0, 'source': '', 'sample': 0}


def _marked(h=40, w=20):
    img = np.full((h, w, 3), 255, np.uint8)
    img[0:5, 0:5] = (10, 20, 30)
    return img


def _worker(front_rotation=0, back_rotation=0):
    return BatchProcessWorker(
        chunks=[], identifier=_FakeIdentifier(front_rotation, back_rotation),
        inspector=CardInspector(), valuator=_FakeValuator(),
    )


def test_front_rotation_reflected_in_returned_images():
    front = _marked()
    result = _worker(front_rotation=90)._process(0, [front])
    corrected = result['images'][0]
    assert not np.array_equal(corrected, front)
    assert np.array_equal(corrected[0:5, -5:], np.full((5, 5, 3), (10, 20, 30), np.uint8))


def test_back_rotation_reflected_independently():
    front, back = _marked(), _marked()
    result = _worker(back_rotation=180)._process(0, [front, back])
    corrected_front, corrected_back = result['images']
    assert np.array_equal(corrected_front, front)   # front_rotation=0, untouched
    assert np.array_equal(corrected_back[-5:, -5:], np.full((5, 5, 3), (10, 20, 30), np.uint8))


def test_no_rotation_is_a_no_op():
    front = _marked()
    result = _worker()._process(0, [front])
    assert np.array_equal(result['images'][0], front)

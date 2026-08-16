import sys

import pytest
from PyQt6.QtWidgets import QApplication

import core.config as config_mod
import core.review_prompt as rp
from ui.main_window import MainWindow


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication(sys.argv)


class _FakeDB:
    """Stands in for Database, returning a fixed collection size."""

    def __init__(self, total):
        self._total = total

    def get_collection_stats(self):
        return {"total_cards": self._total}


class _FakeWindow:
    """Borrows the real methods; supplies only what they actually touch."""

    _card_count = MainWindow._card_count
    _maybe_prompt_review = MainWindow._maybe_prompt_review
    _drain_due_review_prompt = MainWindow._drain_due_review_prompt

    def __init__(self, total):
        self.db = _FakeDB(total)

    def _show_review_prompt(self):
        pass          # QTimer target; never fires without an event loop


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(config_mod, "PREFS_FILE", tmp_path / "prefs.json")


def test_below_threshold_does_not_arm(qapp, isolated):
    _FakeWindow(49)._maybe_prompt_review()
    assert rp.is_due() is False


def test_crossing_threshold_arms(qapp, isolated):
    _FakeWindow(50)._maybe_prompt_review()
    assert rp.is_due() is True


def test_batch_signal_argument_is_accepted(qapp, isolated):
    """cards_added emits an int; card_added emits nothing. Both must work."""
    _FakeWindow(50)._maybe_prompt_review(12)
    assert rp.is_due() is True


def test_already_armed_does_not_rearm(qapp, isolated):
    win = _FakeWindow(50)
    win._maybe_prompt_review()
    rp.mark_prompted(50)              # spends the ask, clears due
    win._maybe_prompt_review()        # a later save must not re-arm
    assert rp.is_due() is False
    assert rp.asks_used() == 1


def test_card_count_survives_a_broken_db(qapp, isolated):
    class Broken:
        def get_collection_stats(self):
            raise RuntimeError("db is down")

    win = _FakeWindow(0)
    win.db = Broken()
    assert win._card_count() == 0     # must not raise — a save must never break
    win._maybe_prompt_review()
    assert rp.is_due() is False


def test_drain_is_a_noop_when_not_due(qapp, isolated):
    _FakeWindow(0)._drain_due_review_prompt()
    assert rp.is_due() is False


def test_armed_prompt_is_not_rearmed(qapp, isolated, monkeypatch):
    """A save arriving while a prompt is armed must not schedule a second one.

    This is the test for the `if is_due(): return` guard specifically. It has to
    arm() directly rather than going through mark_prompted(), because
    mark_prompted clears the due flag — which would leave the guard unreached
    and the test passing for an unrelated reason (the +200 gap), whether or not
    the guard exists at all.
    """
    win = _FakeWindow(50)
    rp.arm()                                  # armed, not yet displayed
    rearmed = []
    monkeypatch.setattr(rp, "arm", lambda: rearmed.append(1))
    win._maybe_prompt_review()
    assert rearmed == []                      # guard short-circuited before arm()

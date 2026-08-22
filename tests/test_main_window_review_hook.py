import sys

import pytest
from PyQt6.QtWidgets import QApplication

import core.config as config_mod
import core.review_prompt as rp
import core.usage as usage_mod
import ui.review_dialog as review_dialog_mod
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
    _show_review_prompt = MainWindow._show_review_prompt

    def __init__(self, total):
        self.db = _FakeDB(total)


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(config_mod, "PREFS_FILE", tmp_path / "prefs.json")


@pytest.fixture
def no_modal(monkeypatch):
    """activeModalWidget() is a QApplication staticmethod; force the no-modal branch."""
    monkeypatch.setattr(QApplication, "activeModalWidget", staticmethod(lambda: None))


@pytest.fixture
def dialog_recorder(monkeypatch):
    """Replaces ReviewPromptDialog with a recorder so no real dialog is constructed."""
    calls = []

    class _RecordingDialog:
        def __init__(self, card_count, parent=None):
            calls.append(card_count)

        def exec(self):
            return 0

    monkeypatch.setattr(review_dialog_mod, "ReviewPromptDialog", _RecordingDialog)
    return calls


@pytest.fixture
def events(monkeypatch):
    """Records usage.log_event calls made via ui.main_window's `usage` import."""
    recorded = []
    monkeypatch.setattr(usage_mod, "log_event",
                         lambda event, **props: recorded.append((event, props)))
    return recorded


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


# ── _show_review_prompt ─────────────────────────────────────────────────────

def test_show_review_prompt_happy_path(qapp, isolated, no_modal, dialog_recorder, events):
    rp.arm()
    win = _FakeWindow(50)
    win._show_review_prompt()
    assert dialog_recorder == [50]
    assert rp.asks_used() == 1
    assert rp.is_due() is False
    assert events == [("review_prompt_shown", {"card_count": 50})]


def test_show_review_prompt_defers_when_modal_is_active(qapp, isolated, dialog_recorder, monkeypatch):
    rp.arm()
    monkeypatch.setattr(QApplication, "activeModalWidget", staticmethod(lambda: object()))
    win = _FakeWindow(50)
    win._show_review_prompt()
    assert dialog_recorder == []
    assert rp.is_due() is True
    assert rp.asks_used() == 0


def test_show_review_prompt_refuses_stale_due_flag(qapp, isolated, no_modal, dialog_recorder):
    """Finding 1: is_due() alone is not enough — a stale flag that survived a
    dismissal, or that outlived the lifetime ceiling, because prefs.json
    couldn't be written (core/config.py logs and swallows OSError on write)
    must not resurrect the dialog. The durable `review_prompt_dismissed` pref
    and the `asks_used() >= MAX_ASKS` ceiling are checked too, not just the
    transient `review_prompt_due` flag."""
    rp.arm()
    config_mod.set_pref("review_prompt_dismissed", True)
    win = _FakeWindow(50)
    win._show_review_prompt()
    assert dialog_recorder == []

    config_mod.set_pref("review_prompt_dismissed", False)
    config_mod.set_pref("review_prompt_count", rp.MAX_ASKS)
    rp.arm()
    win = _FakeWindow(50)
    win._show_review_prompt()
    assert dialog_recorder == []


def test_show_review_prompt_refuses_unreadable_card_count(qapp, isolated, no_modal, dialog_recorder):
    """Finding 2: a failed card-count read must not anchor the repeat gap at 0
    (which would set next_threshold() to REPEAT_GAP and fire a second ask a
    handful of cards later, instead of REPEAT_GAP cards later)."""
    class Broken:
        def get_collection_stats(self):
            raise RuntimeError("db is down")

    rp.arm()
    win = _FakeWindow(0)
    win.db = Broken()
    win._show_review_prompt()
    assert dialog_recorder == []
    assert rp.is_due() is True                      # still armed for a later retry
    assert rp.next_threshold() == rp.FIRST_THRESHOLD  # review_prompt_last_count untouched

import sys

import pytest
from PyQt6.QtWidgets import QApplication

import ui.review_dialog as rd


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication(sys.argv)


@pytest.fixture
def calls(monkeypatch):
    rec = {"declined": [], "rated": 0, "store": 0, "events": []}
    monkeypatch.setattr(rd.review_prompt, "mark_declined",
                        lambda permanent: rec["declined"].append(permanent))
    monkeypatch.setattr(rd.review_prompt, "mark_rated",
                        lambda: rec.update(rated=rec["rated"] + 1))
    monkeypatch.setattr(rd.review_prompt, "open_store_review",
                        lambda: rec.update(store=rec["store"] + 1))
    monkeypatch.setattr(rd.usage, "log_event",
                        lambda event, **props: rec["events"].append((event, props)))
    return rec


def test_escape_resolves_as_not_now(qapp, calls):
    """Escape routes straight to reject() without emitting a close event."""
    rd.ReviewPromptDialog(50).reject()
    assert calls["declined"] == [False]
    assert calls["events"] == [("review_prompt_declined", {"permanent": False})]


def test_window_close_resolves_exactly_once(qapp, calls):
    """The X emits closeEvent, whose default impl then calls reject().

    QDialog.closeEvent()'s default implementation only calls reject() when the
    dialog isVisible() — an unshown dialog's close() accepts the close event
    without ever calling reject(). show() reproduces the real X-button path
    (a dialog is always visible via .exec() before a user can click its X).
    """
    dlg = rd.ReviewPromptDialog(50)
    dlg.show()
    dlg.close()
    assert calls["declined"] == [False]
    assert len(calls["events"]) == 1


def test_not_now_resolves_exactly_once(qapp, calls):
    rd.ReviewPromptDialog(50)._later()
    assert calls["declined"] == [False]
    assert len(calls["events"]) == 1


def test_dont_ask_again_stays_permanent(qapp, calls):
    """_never() declines permanently, then reject() must not overwrite it."""
    rd.ReviewPromptDialog(50)._never()
    assert calls["declined"] == [True]
    assert calls["events"] == [("review_prompt_declined", {"permanent": True})]


def test_rate_logs_no_decline(qapp, calls):
    rd.ReviewPromptDialog(50)._rate()
    assert calls["rated"] == 1
    assert calls["store"] == 1
    assert calls["declined"] == []
    assert calls["events"] == [("review_prompt_rated", {"source": "prompt"})]

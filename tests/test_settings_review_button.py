import sys

import pytest
from PyQt6.QtWidgets import QApplication, QGroupBox, QPushButton

import core.config as config_mod
import core.review_prompt as rp
from ui.settings_dialog import SettingsDialog


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication(sys.argv)


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(config_mod, "PREFS_FILE", tmp_path / "prefs.json")


def test_about_group_is_present(qapp, isolated):
    dlg = SettingsDialog()
    titles = [b.title() for b in dlg.findChildren(QGroupBox)]
    assert "About Lorebox" in titles


def test_rate_button_is_present(qapp, isolated):
    dlg = SettingsDialog()
    labels = [b.text() for b in dlg.findChildren(QPushButton)]
    assert "Rate Lorebox on the Microsoft Store" in labels


def test_button_dispatches_and_dismisses(qapp, isolated, monkeypatch):
    """The Settings path records a permanent dismissal and tags its source.

    open_store_review is stubbed so the test never launches the Store, but
    mark_rated is left real so the prefs write is genuinely exercised.
    """
    opened, events = [], []
    monkeypatch.setattr(rp, "open_store_review", lambda: opened.append(1))
    import core.usage as usage_mod
    monkeypatch.setattr(usage_mod, "log_event",
                        lambda event, **props: events.append((event, props)))

    assert rp.is_dismissed() is False
    SettingsDialog()._open_store_review()

    assert opened == [1]
    assert events == [("review_prompt_rated", {"source": "settings"})]
    assert rp.is_dismissed() is True
    assert rp.should_prompt(10_000) is False   # auto-prompt is now off for good

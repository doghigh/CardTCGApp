"""The Scan tab must NOT enumerate TWAIN scanners at construction (that runs at
app startup and can hang on bad drivers). Enumeration is deferred to showEvent /
the re-detect button."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from unittest.mock import MagicMock

import pytest

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QShowEvent

from ui.scan_tab import ScanTab

_app = QApplication.instance() or QApplication([])


class _CountingScanner:
    def __init__(self):
        self.calls = 0

    def list_sources(self):
        self.calls += 1
        return ["Fake TWAIN Source"]


def _make_tab(scanner):
    return ScanTab(MagicMock(), scanner, MagicMock(), MagicMock(), MagicMock())


def test_sources_not_enumerated_at_construction():
    scanner = _CountingScanner()
    tab = _make_tab(scanner)
    assert scanner.calls == 0, "TWAIN must not be enumerated during construction (startup)"
    # Placeholder is shown until the tab is revealed.
    assert tab.source_combo.count() == 1
    assert "Detecting" in tab.source_combo.itemText(0)


def test_showevent_enumerates_once_then_guards():
    scanner = _CountingScanner()
    tab = _make_tab(scanner)
    assert scanner.calls == 0

    tab.showEvent(QShowEvent())            # first reveal → enumerate
    assert scanner.calls == 1
    assert tab.source_combo.currentText() == "Fake TWAIN Source"

    tab.showEvent(QShowEvent())            # subsequent reveals → guarded, no re-enum
    assert scanner.calls == 1


def test_redetect_button_reenumerates_on_demand():
    scanner = _CountingScanner()
    tab = _make_tab(scanner)
    tab._load_sources()                    # the 🔄 button handler
    tab._load_sources()
    assert scanner.calls == 2              # explicit re-detect always re-runs


def test_no_scanner_shows_friendly_placeholder():
    class _Empty:
        def list_sources(self):
            return []
    tab = _make_tab(_Empty())
    tab._load_sources()
    assert tab.source_combo.currentText() == "(No TWAIN scanner detected)"


def test_enumeration_error_does_not_crash():
    class _Boom:
        def list_sources(self):
            raise RuntimeError("twain driver exploded")
    tab = _make_tab(_Boom())
    tab._load_sources()                    # must swallow the error
    assert tab.source_combo.currentText() == "(No TWAIN scanner detected)"

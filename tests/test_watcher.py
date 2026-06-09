"""Tests for core.watcher — schedule due logic."""

import unittest
from datetime import datetime

from core.watcher import WatchConfig


class WatcherScheduleTests(unittest.TestCase):
    def _cfg(self, **kw):
        c = WatchConfig()
        c.enabled = True
        c.folder = "."          # exists
        for k, v in kw.items():
            setattr(c, k, v)
        return c

    def test_disabled_never_due(self):
        c = self._cfg(enabled=False)
        self.assertFalse(c.is_due(datetime(2026, 6, 5, 15, 0)))

    def test_daily_due_after_time_when_never_run(self):
        c = self._cfg(mode="daily", time="02:00", last_run="")
        self.assertTrue(c.is_due(datetime(2026, 6, 5, 15, 0)))

    def test_daily_not_due_before_time(self):
        c = self._cfg(mode="daily", time="02:00",
                      last_run=datetime(2026, 6, 4, 2, 30).isoformat())
        self.assertFalse(c.is_due(datetime(2026, 6, 5, 1, 0)))

    def test_daily_not_due_if_already_ran_today(self):
        c = self._cfg(mode="daily", time="02:00",
                      last_run=datetime(2026, 6, 5, 2, 30).isoformat())
        self.assertFalse(c.is_due(datetime(2026, 6, 5, 15, 0)))

    def test_daily_due_again_next_day(self):
        c = self._cfg(mode="daily", time="02:00",
                      last_run=datetime(2026, 6, 5, 2, 30).isoformat())
        self.assertTrue(c.is_due(datetime(2026, 6, 6, 15, 0)))

    def test_interval_due_after_window(self):
        c = self._cfg(mode="interval", interval_min=30,
                      last_run=datetime(2026, 6, 5, 15, 0).isoformat())
        self.assertFalse(c.is_due(datetime(2026, 6, 5, 15, 20)))
        self.assertTrue(c.is_due(datetime(2026, 6, 5, 15, 40)))


if __name__ == "__main__":
    unittest.main()

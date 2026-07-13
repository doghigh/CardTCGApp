import core.config as config_mod
import core.trial as trial


def _isolate(tmp_path, monkeypatch):
    # Point prefs at a temp file so the test never touches real user prefs.
    monkeypatch.setattr(config_mod, "PREFS_FILE", tmp_path / "prefs.json")


def test_fresh_install_has_full_trial(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    assert trial.trial_remaining() == trial.TRIAL_LIMIT


def test_consume_decrements_remaining(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    trial.consume_trial()
    trial.consume_trial()
    assert trial.trial_remaining() == trial.TRIAL_LIMIT - 2


def test_remaining_never_negative(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    for _ in range(trial.TRIAL_LIMIT + 3):
        trial.consume_trial()
    assert trial.trial_remaining() == 0

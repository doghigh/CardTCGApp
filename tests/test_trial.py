import core.config as config_mod
import core.trial as trial


def _isolate(tmp_path, monkeypatch):
    # Point prefs at a temp file so the test never touches real user prefs.
    monkeypatch.setattr(config_mod, "PREFS_FILE", tmp_path / "prefs.json")


def _with_limit(monkeypatch, limit):
    # Pin the limit so counter behavior is tested independently of whatever
    # value the shipping build happens to carry (it is 0 while the trial proxy
    # is undeployed).
    monkeypatch.setattr(trial, "TRIAL_LIMIT", limit)


def test_fresh_install_has_full_trial(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _with_limit(monkeypatch, 10)
    assert trial.trial_remaining() == 10


def test_consume_decrements_remaining(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _with_limit(monkeypatch, 10)
    trial.consume_trial()
    trial.consume_trial()
    assert trial.trial_remaining() == 8


def test_remaining_never_negative(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    _with_limit(monkeypatch, 10)
    for _ in range(13):
        trial.consume_trial()
    assert trial.trial_remaining() == 0


def test_zero_limit_offers_no_trial(tmp_path, monkeypatch):
    # Regression: with the trial disabled, a fresh install must report no
    # credits, so identify_card never attempts a proxy round-trip.
    _isolate(tmp_path, monkeypatch)
    _with_limit(monkeypatch, 0)
    assert trial.trial_remaining() == 0

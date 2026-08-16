import core.config as config_mod
import core.review_prompt as rp


def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(config_mod, "PREFS_FILE", tmp_path / "prefs.json")


def test_no_prompt_below_threshold(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    assert rp.should_prompt(0) is False
    assert rp.should_prompt(49) is False


def test_prompts_at_threshold(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    assert rp.should_prompt(50) is True
    assert rp.should_prompt(120) is True


def test_second_ask_requires_gap_after_first(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    rp.mark_prompted(50)
    rp.mark_declined(permanent=False)
    assert rp.should_prompt(249) is False
    assert rp.should_prompt(250) is True


def test_batch_jump_does_not_trigger_immediate_second_ask(tmp_path, monkeypatch):
    """Regression: a 200-card batch import can fire the first ask at 240.

    With an absolute second threshold of 250 the next single card would fire a
    second ask ten cards later. The gap must be relative to the first ask.
    """
    _isolate(tmp_path, monkeypatch)
    rp.mark_prompted(240)
    rp.mark_declined(permanent=False)
    assert rp.should_prompt(250) is False
    assert rp.should_prompt(439) is False
    assert rp.should_prompt(440) is True


def test_no_third_ask_ever(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    rp.mark_prompted(50)
    rp.mark_declined(permanent=False)
    rp.mark_prompted(250)
    rp.mark_declined(permanent=False)
    assert rp.should_prompt(10_000) is False


def test_dont_ask_again_is_permanent(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    rp.mark_prompted(50)
    rp.mark_declined(permanent=True)
    assert rp.should_prompt(10_000) is False


def test_rating_is_permanent(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    rp.mark_prompted(50)
    rp.mark_rated()
    assert rp.should_prompt(10_000) is False


def test_arm_is_idempotent(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    assert rp.is_due() is False
    rp.arm()
    rp.arm()
    assert rp.is_due() is True


def test_mark_prompted_clears_due_and_records_anchor(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    rp.arm()
    rp.mark_prompted(240)
    assert rp.is_due() is False
    assert rp.asks_used() == 1
    assert rp.next_threshold() == 440


def test_decline_clears_due_so_it_does_not_reshow_next_launch(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    rp.arm()
    rp.mark_prompted(50)
    rp.mark_declined(permanent=False)
    assert rp.is_due() is False


def test_corrupt_prefs_values_do_not_crash(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    config_mod.set_pref("review_prompt_count", "not-a-number")
    config_mod.set_pref("review_prompt_last_count", None)
    assert rp.asks_used() == 0
    assert rp.should_prompt(50) is True

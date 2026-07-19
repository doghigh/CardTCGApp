import core.config as config_mod
import core.games as games


def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(config_mod, "PREFS_FILE", tmp_path / "prefs.json")


def test_all_games_defaults_to_builtin(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    assert games.all_games() == games.BUILTIN_GAMES


def test_add_custom_game_appends_after_builtins(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    assert games.add_custom_game("Digimon") is True
    result = games.all_games()
    assert result[: len(games.BUILTIN_GAMES)] == games.BUILTIN_GAMES
    assert result[-1] == "Digimon"
    assert games.get_custom_games() == ["Digimon"]


def test_empty_or_whitespace_rejected(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    assert games.add_custom_game("   ") is False
    assert games.add_custom_game("") is False
    assert games.get_custom_games() == []


def test_dedupe_is_case_insensitive(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    assert games.add_custom_game("baseball") is False    # shadows a built-in
    assert games.add_custom_game("Digimon") is True
    assert games.add_custom_game("digimon") is False     # case-insensitive dup
    assert games.get_custom_games() == ["Digimon"]


def test_persistence_roundtrip(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    games.add_custom_game("Sorcery")
    assert "Sorcery" in games.get_custom_games()
    assert "Sorcery" in games.all_games()

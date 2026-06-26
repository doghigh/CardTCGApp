import importlib

def test_token_is_stable_and_urlsafe(tmp_path, monkeypatch):
    # Point APP_DIR at a temp dir so we don't touch the real config.
    monkeypatch.setenv("APPDATA", str(tmp_path))
    import core.config as config_mod
    importlib.reload(config_mod)
    cfg = config_mod.AppConfig()

    t1 = cfg.get_or_create_sync_token()
    t2 = cfg.get_or_create_sync_token()
    assert t1 == t2                      # stable
    assert len(t1) >= 32                 # token_urlsafe(32) -> ~43 chars
    # A freshly constructed config reads the same persisted token.
    assert config_mod.AppConfig().get_or_create_sync_token() == t1

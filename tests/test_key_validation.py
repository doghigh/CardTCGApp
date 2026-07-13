from core.key_validation import validate_anthropic_key


class _OKClient:
    def __init__(self, key): pass
    class models:
        @staticmethod
        def list(): return ["claude-haiku-4-5-20251001"]


def _factory_raising(exc):
    def factory(key):
        class C:
            class models:
                @staticmethod
                def list(): raise exc
        return C()
    return factory


def test_blank_key_is_invalid():
    ok, msg = validate_anthropic_key("   ")
    assert ok is False and msg


def test_valid_key_passes():
    ok, msg = validate_anthropic_key("sk-good", client_factory=lambda k: _OKClient(k))
    assert ok is True and msg == ""


def test_rejected_key_reports_clearly():
    ok, msg = validate_anthropic_key("sk-bad",
                                     client_factory=_factory_raising(Exception("401 unauthorized")))
    assert ok is False and "key" in msg.lower()

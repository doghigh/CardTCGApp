"""Validate an Anthropic API key with a lightweight, side-effect-free call."""
import logging

logger = logging.getLogger(__name__)


def validate_anthropic_key(key: str, client_factory=None) -> tuple:
    """Return (ok, message). ok=True means the key authenticated successfully."""
    key = (key or "").strip()
    if not key:
        return False, "Please paste a key first."

    if client_factory is None:
        try:
            import anthropic
        except ImportError:
            return False, "Anthropic library is unavailable."
        client_factory = lambda k: anthropic.Anthropic(api_key=k)

    try:
        client = client_factory(key)
        client.models.list()  # cheap authenticated call
        return True, ""
    except Exception as exc:  # noqa: BLE001 — normalize to a friendly message
        text = str(exc).lower()
        if "401" in text or "unauthor" in text or "authentication" in text or "invalid" in text:
            return False, "That key was rejected. Double-check you copied it correctly."
        logger.warning("Key validation could not reach Anthropic: %s", exc)
        return False, "Couldn't reach Anthropic to verify the key. Check your connection and try again."

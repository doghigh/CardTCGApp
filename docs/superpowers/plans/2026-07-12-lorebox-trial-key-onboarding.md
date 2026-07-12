# Free-Trial + Streamlined Key Onboarding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a brand-new user scan and auto-identify ~10 cards with zero setup (via a cost-capped Cloudflare Worker holding the developer's Anthropic key), then present a fast deep-link + paste-and-validate dialog to add their own key — removing the upfront signup wall.

**Architecture:** Trial scans route through a Cloudflare Worker that injects the developer's key and enforces a global monthly spend cap in KV; a user with their own `ANTHROPIC_API_KEY` bypasses the Worker entirely and calls Anthropic directly (unchanged). A local per-install counter (advisory) decides when to show the "add your own key" dialog. Routing lives in `core/identifier.py`; the local counter and Worker URL live in a new `core/trial.py`.

**Tech Stack:** Python 3.11 / PyQt6 desktop (existing); Cloudflare Workers + Workers KV (new, JavaScript); `anthropic` Python SDK (already pinned `anthropic==0.105.2`); pytest (existing test suite, 51 tests).

## Global Constraints

- Python deps must stay minimal — **no new Python runtime dependency**; reuse the pinned `anthropic==0.105.2` SDK and stdlib only.
- Trial size: **10 identifications per install** (`TRIAL_LIMIT = 10`).
- Global spend cap: **$100/month** budget → `MONTHLY_TRIAL_CAP` ≈ **16600** identifications at ~$0.006 each (Worker binding, not shipped in the app).
- Worker stores **nothing but the monthly integer counter** — no card images, no responses, no request logging of payloads.
- Vision model stays `claude-haiku-4-5-20251001` (matches existing `core/identifier.py:149`).
- A trial credit is consumed **only on a confirmed successful identification** — never on any failure.
- BYO-key path must remain byte-for-byte the existing direct-to-Anthropic behavior.
- Windows-first desktop app; keep `%APPDATA%/Lorebox` storage conventions (`core/config.py`).

---

## File Structure

**New — Cloudflare Worker (`trial-proxy/`):**
- `trial-proxy/src/index.js` — the Worker: transparent `POST /v1/messages` relay + cap enforcement.
- `trial-proxy/src/cap.js` — pure helpers (`monthKey`, `isOverCap`) so cap logic is unit-testable without network/KV.
- `trial-proxy/test/cap.test.js` — `node:test` unit tests for the pure helpers (no npm install required).
- `trial-proxy/wrangler.toml` — Worker config (KV binding, vars).
- `trial-proxy/README.md` — deploy + secret-setting steps.

**New — desktop core:**
- `core/trial.py` — local trial counter (prefs-backed), Worker URL constant, trial exceptions.
- `core/key_validation.py` — `validate_anthropic_key()` (testable, factory-injectable).

**New — desktop UI:**
- `ui/key_setup_dialog.py` — streamlined deep-link + paste-and-validate dialog.

**Modified — desktop:**
- `core/identifier.py` — three-way routing (own key / trial-proxy / blocked) + typed trial handling.
- `ui/scan_tab.py` — on a trial-blocked scan result, request the key-setup dialog.
- `ui/main_window.py` — delete the upfront key prompt; wire the key-setup dialog.

**New — tests:**
- `tests/test_trial.py` — local counter + remaining/consume.
- `tests/test_identifier_routing.py` — the three-way routing decision + no-consume-on-failure.
- `tests/test_key_validation.py` — valid / rejected / unreachable.

---

## Phase A — Cloudflare Worker (trial proxy)

### Task A1: Pure cap helpers + unit tests

**Files:**
- Create: `trial-proxy/src/cap.js`
- Test: `trial-proxy/test/cap.test.js`

**Interfaces:**
- Produces: `monthKey(date: Date) -> string` (e.g. `"trial:2026-07"`); `isOverCap(count: number, cap: number) -> boolean`.

- [ ] **Step 1: Write the failing test**

```js
// trial-proxy/test/cap.test.js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { monthKey, isOverCap } from '../src/cap.js';

test('monthKey formats year-month, zero-padded', () => {
  assert.equal(monthKey(new Date(Date.UTC(2026, 6, 12))), 'trial:2026-07');
  assert.equal(monthKey(new Date(Date.UTC(2026, 0, 3))), 'trial:2026-01');
});

test('isOverCap is true only at or above the cap', () => {
  assert.equal(isOverCap(0, 10), false);
  assert.equal(isOverCap(9, 10), false);
  assert.equal(isOverCap(10, 10), true);
  assert.equal(isOverCap(11, 10), true);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test trial-proxy/test/`
Expected: FAIL — cannot find module `../src/cap.js`.

- [ ] **Step 3: Write minimal implementation**

```js
// trial-proxy/src/cap.js
export function monthKey(date) {
  const y = date.getUTCFullYear();
  const m = String(date.getUTCMonth() + 1).padStart(2, '0');
  return `trial:${y}-${m}`;
}

export function isOverCap(count, cap) {
  return count >= cap;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test trial-proxy/test/`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add trial-proxy/src/cap.js trial-proxy/test/cap.test.js
git commit -m "feat(trial-proxy): pure cap helpers (monthKey, isOverCap) + tests"
```

---

### Task A2: Worker relay + cap enforcement

**Files:**
- Create: `trial-proxy/src/index.js`
- Create: `trial-proxy/wrangler.toml`
- Create: `trial-proxy/README.md`

**Interfaces:**
- Consumes: `monthKey`, `isOverCap` from `src/cap.js`.
- Produces: an HTTP endpoint `POST /v1/messages` that the desktop `anthropic` SDK targets via `base_url`. Returns Anthropic's response on success, or `429` with body `{"type":"error","error":{"type":"trial_capacity","message":"..."}}` when the monthly cap is reached.

- [ ] **Step 1: Write the Worker**

```js
// trial-proxy/src/index.js
import { monthKey, isOverCap } from './cap.js';

const ANTHROPIC_URL = 'https://api.anthropic.com/v1/messages';
const ANTHROPIC_VERSION = '2023-06-01';

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (request.method !== 'POST' || url.pathname !== '/v1/messages') {
      return json(404, { type: 'error', error: { type: 'not_found', message: 'not found' } });
    }

    const cap = parseInt(env.MONTHLY_TRIAL_CAP, 10);
    const key = monthKey(new Date());
    const count = parseInt((await env.TRIAL_KV.get(key)) || '0', 10);

    if (isOverCap(count, cap)) {
      return json(429, {
        type: 'error',
        error: { type: 'trial_capacity', message: 'Free trial is at capacity this month.' },
      });
    }

    // Relay the request body verbatim, injecting the developer's key.
    const body = await request.text();
    const upstream = await fetch(ANTHROPIC_URL, {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        'x-api-key': env.ANTHROPIC_API_KEY,
        'anthropic-version': ANTHROPIC_VERSION,
      },
      body,
    });

    // Count only confirmed successes. KV is eventually consistent; acceptable
    // for a coarse monthly $ cap.
    if (upstream.ok) {
      await env.TRIAL_KV.put(key, String(count + 1));
    }

    // Pass the upstream response straight back. No payload logging anywhere.
    return new Response(upstream.body, {
      status: upstream.status,
      headers: { 'content-type': upstream.headers.get('content-type') || 'application/json' },
    });
  },
};

function json(status, obj) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}
```

- [ ] **Step 2: Write the wrangler config**

```toml
# trial-proxy/wrangler.toml
name = "lorebox-trial"
main = "src/index.js"
compatibility_date = "2026-07-01"

# MONTHLY_TRIAL_CAP: $100/month budget / ~$0.006 per identification ≈ 16600.
# Re-derive if per-identification cost changes.
[vars]
MONTHLY_TRIAL_CAP = "16600"

# Create with: wrangler kv namespace create TRIAL_KV
# then paste the returned id below.
[[kv_namespaces]]
binding = "TRIAL_KV"
id = "REPLACE_WITH_KV_NAMESPACE_ID"
```

- [ ] **Step 3: Write the deploy README**

```markdown
# LoreBox trial proxy (Cloudflare Worker)

Relays trial card-identification requests to Anthropic using the developer's
key, and enforces a global monthly spend cap. Users with their own key never
touch this service.

## Deploy

1. `npm i -g wrangler` (or use `npx wrangler`).
2. `wrangler kv namespace create TRIAL_KV` → paste the `id` into `wrangler.toml`.
3. Set the developer's Anthropic key as a secret (never commit it):
   `wrangler secret put ANTHROPIC_API_KEY`
4. (Optional) adjust `MONTHLY_TRIAL_CAP` in `wrangler.toml`.
5. `wrangler deploy` → note the `https://lorebox-trial.<subdomain>.workers.dev`
   URL and put it in `core/trial.py`'s `WORKER_BASE_URL`.
6. Add a Cloudflare billing alert as a secondary safety net.

## Verify locally

`wrangler dev` then POST an Anthropic-shaped body to `/v1/messages` with any
`x-api-key` header (the Worker replaces it). Confirm a 200 relays through and
the KV counter increments; set `MONTHLY_TRIAL_CAP="0"` to confirm the 429.

The Worker logs no request/response bodies — only the monthly integer counter
is persisted.
```

- [ ] **Step 4: Verify pure logic still passes**

Run: `node --test trial-proxy/test/`
Expected: PASS (A1 tests unaffected).

- [ ] **Step 5: Commit**

```bash
git add trial-proxy/src/index.js trial-proxy/wrangler.toml trial-proxy/README.md
git commit -m "feat(trial-proxy): Anthropic relay Worker with monthly KV cap"
```

> **Note:** the live `fetch` handler is verified manually via `wrangler dev`
> (README step "Verify locally") rather than a miniflare harness, to keep the
> JS footprint to zero npm dependencies. The cap decision logic it depends on
> is unit-tested in Task A1.

---

## Phase B — Desktop trial core + routing

### Task B1: Local trial counter (`core/trial.py`)

**Files:**
- Create: `core/trial.py`
- Test: `tests/test_trial.py`

**Interfaces:**
- Produces:
  - `TRIAL_LIMIT: int = 10`
  - `WORKER_BASE_URL: str` (deployed Worker origin, no trailing path)
  - `trial_remaining() -> int`
  - `consume_trial() -> None`
  - `class TrialCapacityReached(Exception)`
  - `class TrialUnavailable(Exception)`
- Consumes: `core.config.get_pref` / `set_pref` (prefs are non-secret; the counter is advisory).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_trial.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_trial.py -v`
Expected: FAIL — `No module named 'core.trial'`.

- [ ] **Step 3: Write minimal implementation**

```python
# core/trial.py
"""Local, advisory free-trial counter + trial-proxy routing constants.

The per-install counter lives in (non-secret) prefs and is deliberately
resettable — it only decides when to show the "add your own key" dialog.
Actual spend is bounded server-side by the Worker's monthly cap.
"""
from core.config import get_pref, set_pref

TRIAL_LIMIT = 10

# Set to the deployed Cloudflare Worker origin (see trial-proxy/README.md).
# The anthropic SDK appends "/v1/messages", so this is the origin only.
WORKER_BASE_URL = "https://lorebox-trial.REPLACE.workers.dev"

_PREF_KEY = "trial_used"


class TrialCapacityReached(Exception):
    """The global monthly trial cap is exhausted (Worker returned 429)."""


class TrialUnavailable(Exception):
    """The trial proxy could not be reached or returned an unexpected error."""


def trial_remaining() -> int:
    used = int(get_pref(_PREF_KEY, 0) or 0)
    return max(0, TRIAL_LIMIT - used)


def consume_trial() -> None:
    used = int(get_pref(_PREF_KEY, 0) or 0)
    set_pref(_PREF_KEY, used + 1)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_trial.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add core/trial.py tests/test_trial.py
git commit -m "feat(trial): local advisory trial counter + routing constants"
```

---

### Task B2: Three-way routing in `core/identifier.py`

**Files:**
- Modify: `core/identifier.py` (`_get_client` → routing; `identify_card`; `_identify_with_claude`)
- Test: `tests/test_identifier_routing.py`

**Interfaces:**
- Consumes: `core.trial.trial_remaining`, `consume_trial`, `WORKER_BASE_URL`, `TrialCapacityReached`, `TrialUnavailable`.
- Produces: `CardIdentifier.identify_card(front, back=None) -> Dict` where `dict['source']` is one of `'claude'`, `'ocr'`, `'trial_exhausted'`, `'trial_capacity'`, `'trial_unavailable'`. On any `trial_*` source all card fields are `None`. Adds `CardIdentifier._resolve_client() -> tuple[object | None, str]` returning `(client, mode)` with `mode` in `{'own', 'trial', 'none'}`.

> **Design note (deviation from spec):** the spec described raising
> `TrialExhausted` to the caller. There are 5 `identify_card` call sites that
> already branch on the returned `dict['source']` (`'claude'` vs `'ocr'`);
> returning a `source` marker instead of raising keeps that single contract,
> is DRYer, and lower-risk. Product behavior is identical — the interactive
> scan path (Task C3) shows the key dialog on any `trial_*` source.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_identifier_routing.py
import numpy as np
import pytest

import core.trial as trial
from core.identifier import CardIdentifier


@pytest.fixture
def img():
    return np.zeros((10, 10, 3), dtype=np.uint8)


def test_own_key_calls_direct_and_does_not_consume(monkeypatch, img):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-real")
    ident = CardIdentifier()
    monkeypatch.setattr(ident, "_identify_with_claude",
                        lambda f, b: {"name": "Black Lotus"})
    consumed = {"n": 0}
    monkeypatch.setattr(trial, "consume_trial", lambda: consumed.__setitem__("n", consumed["n"] + 1))

    out = ident.identify_card(img)
    assert out["source"] == "claude"
    assert consumed["n"] == 0  # own key never touches the trial counter


def test_trial_success_consumes_one_credit(monkeypatch, img):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(trial, "trial_remaining", lambda: 5)
    consumed = {"n": 0}
    monkeypatch.setattr(trial, "consume_trial", lambda: consumed.__setitem__("n", consumed["n"] + 1))
    ident = CardIdentifier()
    monkeypatch.setattr(ident, "_identify_with_claude", lambda f, b: {"name": "Shivan Dragon"})

    out = ident.identify_card(img)
    assert out["source"] == "claude"
    assert consumed["n"] == 1


def test_trial_exhausted_makes_no_call(monkeypatch, img):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(trial, "trial_remaining", lambda: 0)
    ident = CardIdentifier()
    called = {"n": 0}
    monkeypatch.setattr(ident, "_identify_with_claude",
                        lambda f, b: called.__setitem__("n", called["n"] + 1))

    out = ident.identify_card(img)
    assert out["source"] == "trial_exhausted"
    assert called["n"] == 0


def test_trial_capacity_does_not_consume(monkeypatch, img):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(trial, "trial_remaining", lambda: 5)
    consumed = {"n": 0}
    monkeypatch.setattr(trial, "consume_trial", lambda: consumed.__setitem__("n", consumed["n"] + 1))
    ident = CardIdentifier()

    def raise_capacity(f, b):
        raise trial.TrialCapacityReached()
    monkeypatch.setattr(ident, "_identify_with_claude", raise_capacity)

    out = ident.identify_card(img)
    assert out["source"] == "trial_capacity"
    assert consumed["n"] == 0


def test_trial_unavailable_does_not_consume(monkeypatch, img):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(trial, "trial_remaining", lambda: 5)
    consumed = {"n": 0}
    monkeypatch.setattr(trial, "consume_trial", lambda: consumed.__setitem__("n", consumed["n"] + 1))
    ident = CardIdentifier()

    def raise_unavailable(f, b):
        raise trial.TrialUnavailable()
    monkeypatch.setattr(ident, "_identify_with_claude", raise_unavailable)

    out = ident.identify_card(img)
    assert out["source"] == "trial_unavailable"
    assert consumed["n"] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_identifier_routing.py -v`
Expected: FAIL — `identify_card` does not return `trial_*` sources / `_resolve_client` missing.

- [ ] **Step 3: Write the implementation**

Replace `_get_client` (lines 84–92) with a routing resolver, and rewrite `identify_card` (lines 102–124). Add the import at the top of `core/identifier.py`:

```python
from core import trial
```

Replace `_get_client` with:

```python
    def _resolve_client(self):
        """Return (client, mode). mode is 'own', 'trial', or 'none'.

        'own'  — user supplied ANTHROPIC_API_KEY; call Anthropic directly.
        'trial'— no user key but trial credits remain; route via the Worker.
        'none' — no key and no trial credits left.
        """
        if not HAS_ANTHROPIC:
            return None, 'none'
        api_key = os.environ.get('ANTHROPIC_API_KEY')
        if api_key:
            if self._anthropic is None:
                self._anthropic = anthropic.Anthropic(api_key=api_key)
            return self._anthropic, 'own'
        if trial.trial_remaining() > 0:
            # Placeholder key — the Worker injects the real one. base_url is the
            # Worker origin; the SDK appends "/v1/messages".
            client = anthropic.Anthropic(api_key='trial-proxy',
                                         base_url=trial.WORKER_BASE_URL)
            return client, 'trial'
        return None, 'none'
```

Replace `identify_card` with:

```python
    def identify_card(self, front_img: np.ndarray,
                      back_img: Optional[np.ndarray] = None) -> Dict:
        """Identify a card. See module docstring for 'source' semantics.

        'source' is one of: 'claude' (genuine vision id, direct or trial-proxied),
        'ocr' (degraded Tesseract fallback), or a 'trial_*' marker meaning the
        trial is blocked and the UI should offer the add-your-own-key dialog.
        """
        client, mode = self._resolve_client()

        if mode == 'none':
            return self._trial_blocked('trial_exhausted')

        if mode == 'trial':
            try:
                result = self._identify_with_claude(front_img, back_img,
                                                    client=client, trial_mode=True)
            except trial.TrialCapacityReached:
                return self._trial_blocked('trial_capacity')
            except trial.TrialUnavailable:
                return self._trial_blocked('trial_unavailable')
            if result and result.get('name'):
                trial.consume_trial()
                result['source'] = 'claude'
                return result
            # Reached the proxy but got no usable data — treat as unavailable,
            # do not consume a credit, do not fabricate via OCR.
            return self._trial_blocked('trial_unavailable')

        # mode == 'own': existing behavior, unchanged.
        result = self._identify_with_claude(front_img, back_img, client=client)
        if result and result.get('name'):
            result['source'] = 'claude'
            return result
        front_text = self.extract_text(front_img)
        back_text = self.extract_text(back_img) if back_img is not None else ""
        header_text = self.extract_header_text(back_img) if back_img is not None else ""
        info = self.parse_card_info(front_text, back_text, header_text)
        info['source'] = 'ocr'
        return info

    @staticmethod
    def _trial_blocked(reason: str) -> Dict:
        return {'name': None, 'set_name': None, 'card_number': None,
                'rarity': None, 'year': None, 'game': None, 'source': reason}
```

Update `_identify_with_claude`'s signature and error handling (lines 130–177) so it accepts the resolved client and, in trial mode, translates proxy errors into typed exceptions. Change the signature line to:

```python
    def _identify_with_claude(self, front_img: np.ndarray,
                               back_img: Optional[np.ndarray] = None,
                               client=None, trial_mode: bool = False) -> Optional[Dict]:
        if client is None:
            client = self._resolve_client()[0]
        if client is None:
            return None
```

Then replace the trailing `except Exception as e:` block (lines 175–177) with:

```python
        except Exception as e:
            if trial_mode:
                status = getattr(e, "status_code", None)
                body = getattr(e, "body", None)
                etype = ""
                if isinstance(body, dict):
                    etype = (body.get("error") or {}).get("type", "")
                if status == 429 and etype == "trial_capacity":
                    raise trial.TrialCapacityReached() from e
                raise trial.TrialUnavailable() from e
            logger.warning("Claude vision error: %s", e)
            return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_identifier_routing.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Run the full suite (no regressions)**

Run: `python -m pytest tests/ -q`
Expected: PASS (previously 51 + new tests).

- [ ] **Step 6: Commit**

```bash
git add core/identifier.py tests/test_identifier_routing.py
git commit -m "feat(identifier): route scans via trial proxy when no user key"
```

---

## Phase C — Desktop UI

### Task C1: `validate_anthropic_key()` (`core/key_validation.py`)

**Files:**
- Create: `core/key_validation.py`
- Test: `tests/test_key_validation.py`

**Interfaces:**
- Produces: `validate_anthropic_key(key: str, client_factory=None) -> tuple[bool, str]` — `(True, "")` on success; `(False, message)` on a rejected key or an unreachable service. `client_factory(key)` builds a client exposing `.models.list()`; defaults to the real `anthropic.Anthropic`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_key_validation.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_key_validation.py -v`
Expected: FAIL — `No module named 'core.key_validation'`.

- [ ] **Step 3: Write minimal implementation**

```python
# core/key_validation.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_key_validation.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add core/key_validation.py tests/test_key_validation.py
git commit -m "feat(keys): validate_anthropic_key with a light authenticated call"
```

---

### Task C2: `KeySetupDialog` (`ui/key_setup_dialog.py`)

**Files:**
- Create: `ui/key_setup_dialog.py`

**Interfaces:**
- Consumes: `core.key_validation.validate_anthropic_key`, `core.config.config`.
- Produces: `class KeySetupDialog(QDialog)` with `__init__(self, parent=None, reason: str = 'trial_exhausted')`. On a validated key it calls `config.save({'ANTHROPIC_API_KEY': key})` and `self.accept()`; "Maybe later" calls `self.reject()`. Deep-link button opens `https://console.anthropic.com/settings/keys`.

- [ ] **Step 1: Implement the dialog**

```python
# ui/key_setup_dialog.py
"""Streamlined 'add your own Anthropic key' dialog.

Shown when the free trial is used up (or at capacity). Three actions:
deep-link to the console keys page, paste-and-validate inline, or defer.
"""
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton
)

from core.config import config
from core.key_validation import validate_anthropic_key

CONSOLE_KEYS_URL = "https://console.anthropic.com/settings/keys"

_HEADLINES = {
    'trial_exhausted': "You've used your 10 free card identifications.",
    'trial_capacity':  "The free trial is at capacity right now.",
    'trial_unavailable': "The free trial service is temporarily unavailable.",
    'first_run': "Add an Anthropic key to auto-identify your cards.",
}


class KeySetupDialog(QDialog):
    def __init__(self, parent=None, reason: str = 'trial_exhausted'):
        super().__init__(parent)
        self.setWindowTitle("Add your Anthropic key")
        self.setMinimumWidth(460)

        v = QVBoxLayout(self)
        v.setContentsMargins(22, 22, 22, 22)
        v.setSpacing(12)

        headline = _HEADLINES.get(reason, _HEADLINES['trial_exhausted'])
        msg = QLabel(
            f"<b>{headline}</b><br><br>"
            "To keep scanning, add your own free Anthropic key — it's about "
            "$0.006 per card. Once added, scanning goes directly to Anthropic; "
            "nothing passes through us."
        )
        msg.setWordWrap(True)
        v.addWidget(msg)

        get_btn = QPushButton("Get a key (opens browser)…")
        get_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(CONSOLE_KEYS_URL)))
        v.addWidget(get_btn)

        self.key_edit = QLineEdit()
        self.key_edit.setPlaceholderText("Paste your API key here")
        self.key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        v.addWidget(self.key_edit)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        v.addWidget(self.status)

        row = QHBoxLayout()
        later = QPushButton("Maybe later")
        later.clicked.connect(self.reject)
        row.addWidget(later)
        row.addStretch()
        self.save_btn = QPushButton("Validate & Save")
        self.save_btn.setProperty("primary", True)
        self.save_btn.setDefault(True)
        self.save_btn.clicked.connect(self._validate_and_save)
        row.addWidget(self.save_btn)
        v.addLayout(row)

    def _validate_and_save(self):
        self.save_btn.setEnabled(False)
        self.status.setText("Checking…")
        # Process the label update before the (blocking) network call.
        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()

        key = self.key_edit.text()
        ok, message = validate_anthropic_key(key)
        if ok:
            config.save({"ANTHROPIC_API_KEY": key.strip()})
            self.accept()
            return
        self.status.setText(f"⚠ {message}")
        self.save_btn.setEnabled(True)
```

- [ ] **Step 2: Import-smoke check**

Run: `python -c "import ui.key_setup_dialog"`
Expected: no output, exit 0 (module imports cleanly).

- [ ] **Step 3: Commit**

```bash
git add ui/key_setup_dialog.py
git commit -m "feat(ui): streamlined deep-link + paste-and-validate key dialog"
```

---

### Task C3: Trigger the dialog from a blocked scan (`ui/scan_tab.py`)

**Files:**
- Modify: `ui/scan_tab.py` (add signal + handle `trial_*` sources after identify at line 460)

**Interfaces:**
- Consumes: `identify_card`'s `dict['source']` `trial_*` markers.
- Produces: `ScanTab.key_setup_requested = pyqtSignal(str)` emitted with the trial reason when a scan is trial-blocked. (Wired to the dialog in Task C4.)

- [ ] **Step 1: Add the signal**

In `ui/scan_tab.py`, next to the existing signals (around line 94), add:

```python
    key_setup_requested = pyqtSignal(str)
```

- [ ] **Step 2: Handle a blocked result after identify**

At the identify call site (`ui/scan_tab.py:460`), immediately after `info = self.identifier.identify_card(...)`, insert:

```python
            source = (info or {}).get('source', '')
            if source.startswith('trial_'):
                self.status_label.setText(
                    "Free trial used — add your own key to keep auto-identifying."
                )
                self.key_setup_requested.emit(source)
                return
```

> The `return` stops this scan from applying empty (`name=None`) trial-blocked
> data over the card form. The user's scanned image remains; they can add a key
> and scan again, or enter details manually.

- [ ] **Step 3: Import-smoke check**

Run: `python -c "import ui.scan_tab"`
Expected: exit 0.

- [ ] **Step 4: Commit**

```bash
git add ui/scan_tab.py
git commit -m "feat(scan): offer key setup when a scan is trial-blocked"
```

---

### Task C4: First-run cleanup + dialog wiring (`ui/main_window.py`)

**Files:**
- Modify: `ui/main_window.py` (delete `_prompt_for_keys_if_needed`; wire `key_setup_requested`)

**Interfaces:**
- Consumes: `ScanTab.key_setup_requested`, `ui.key_setup_dialog.KeySetupDialog`.
- Produces: `MainWindow._open_key_setup(reason: str)`.

- [ ] **Step 1: Delete the upfront key prompt**

In `ui/main_window.py`, remove the call at line 119:

```python
        self._prompt_for_keys_if_needed()
```

and delete the entire `_prompt_for_keys_if_needed` method (lines 163–177). The welcome notice (`_show_first_run_notice`) stays.

- [ ] **Step 2: Wire the scan-tab signal to the dialog**

Where `scan_tab` signals are connected (near line 73, after the existing `open_settings_requested` connect), add:

```python
        self.scan_tab.key_setup_requested.connect(self._open_key_setup)
```

- [ ] **Step 3: Add the handler**

Add this method to `MainWindow` (near `_open_settings`, line 353):

```python
    def _open_key_setup(self, reason: str):
        from ui.key_setup_dialog import KeySetupDialog
        dlg = KeySetupDialog(self, reason=reason)
        if dlg.exec() == 1:  # Accepted — a key was validated and saved
            self.identifier.reload_credentials()
            self.valuator.reload_credentials()
            self.scan_tab.refresh_api_key_banner()
            self.statusBar().showMessage("✅ API key added — auto-identify is on", 3000)
```

- [ ] **Step 4: Import-smoke check**

Run: `python -c "import ui.main_window"`
Expected: exit 0.

- [ ] **Step 5: Run the full suite**

Run: `python -m pytest tests/ -q`
Expected: PASS (51 original + new tests, no regressions).

- [ ] **Step 6: Commit**

```bash
git add ui/main_window.py
git commit -m "feat(onboarding): drop upfront key wall; wire trial key-setup dialog"
```

---

## Phase D — Deploy-time follow-ups (not code; do at rollout)

These are tracked here so they aren't lost; they are **not** implementation
tasks for the plan executor.

- [ ] Deploy the Worker (`trial-proxy/README.md`), set the `ANTHROPIC_API_KEY`
      secret and the `TRIAL_KV` namespace id, then paste the live URL into
      `core/trial.py`'s `WORKER_BASE_URL` and commit that one-line change.
- [ ] Add a Cloudflare billing alert / Anthropic usage alert as a secondary
      spend safety net independent of the KV counter.
- [ ] Update `PRIVACY.md` + the site's privacy page to distinguish trial
      (relayed through LoreBox's server, not stored) from BYO-key (direct to
      Anthropic). Separate reviewable change — flag the exact lines then.
- [ ] Bump `APP_VERSION` / Store manifests for the release that includes this.

---

## Self-Review

**Spec coverage:**
- Bounded trial (10/install) → B1. ✅
- Global monthly $ cap in KV → A1 (logic) + A2 (enforcement). ✅
- Three-way routing (own/trial/none) → B2. ✅
- Credit consumed only on success; never on failure → B2 tests. ✅
- Zero-logging relay Worker → A2 (no body logging; README states it). ✅
- Streamlined deep-link + paste-and-validate dialog → C1 + C2. ✅
- Remove upfront first-run key prompt → C4. ✅
- Trigger dialog at trial exhaustion → C3 + C4. ✅
- Distinct honest failure messages (unavailable / capacity / exhausted) →
  B2 (`trial_*` sources) + C2 (`_HEADLINES`) + C3 (status text). ✅
- Privacy reconciliation copy (in-app) → C2 dialog body ("nothing passes
  through us"); site/PRIVACY.md deferred → Phase D. ✅
- Testing (Worker cap, routing, no-consume-on-failure, validation) →
  A1, B2, C1. ✅

**Placeholder scan:** `WORKER_BASE_URL` and the `wrangler.toml` KV `id` are
intentional deploy-time fill-ins, called out in Phase D — not plan
placeholders. No "TBD"/"add error handling"/"write tests for the above"
left in any step.

**Type consistency:** `_resolve_client() -> (client, mode)` with modes
`'own'|'trial'|'none'` is defined in B2 and used only there. `identify_card`'s
`source` values (`'claude'|'ocr'|'trial_exhausted'|'trial_capacity'|
'trial_unavailable'`) are produced in B2 and consumed in C3 (`startswith
'trial_'`) and named in C2's `_HEADLINES`. `validate_anthropic_key(key,
client_factory=None) -> (bool, str)` matches between C1 and its use in C2.
`consume_trial`/`trial_remaining`/`TrialCapacityReached`/`TrialUnavailable`
defined in B1, used in B2. Consistent.

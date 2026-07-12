# LoreBox — Free-Trial Identifications + Streamlined Key Onboarding

**Date:** 2026-07-12
**Status:** Design approved, pending spec review
**Author:** Jesse + Claude

## Problem

New users open LoreBox and, within the first ~45 seconds, hit two blocking
modals before getting any value: a welcome notice, then a prompt to go sign up
for an Anthropic API key (`ui/main_window.py:118-119`,
`_prompt_for_keys_if_needed`). The flagship feature — scan a card and have it
auto-identified — is gated behind an external signup + billing detour that
happens *before* the user has scanned a single card. This is a classic
onboarding bounce: "do homework before you can try it."

We cannot automate the account signup itself — there is no API to create an
Anthropic Console or eBay Developer account on a user's behalf, and scripting
their signup/billing forms with their credentials is out of scope (both a
terms violation and a credential-handling boundary we won't cross).

## Goal

Flip the arc from *"do homework before you can try it"* to *"try it, love it,
then it asks."* Two coordinated changes:

1. **Bounded free trial** — ship 10 free card identifications that work with
   zero setup, using a key the developer controls, cost-capped server-side.
2. **Streamlined BYO-key flow** — when the trial runs out (or any time a user
   wants their own key), a fast deep-link + paste-and-validate dialog replaces
   the current generic prompt → full Settings dialog detour.

The existing bring-your-own-key / no-account / nothing-uploaded model is
**preserved**. The trial is additive; the instant a user adds their own key,
the app reverts to the current direct-to-Anthropic architecture and the
developer's costs stop.

## Non-goals

- Automating provider account creation (impossible / out of scope).
- Changing the eBay valuation key flow — it stays in full Settings; it's
  optional and MTG already prices via Scryfall with no key.
- Server-side per-install tracking, device fingerprinting, or any persistent
  user identifier. (See "Abuse model" — we deliberately don't do this.)

## Architecture

```
Desktop app (no own key, trial > 0)  →  Cloudflare Worker  →  Anthropic API
                                         (holds DEV key,
                                          enforces global cap)

Desktop app (own key)                →  Anthropic API directly   (unchanged)
```

The Worker is **only** in the request path for trial users. A user with their
own `ANTHROPIC_API_KEY` never touches it — unlimited, direct, nothing uploaded
to the developer.

### Why Cloudflare Workers + KV

The existing `ebay_webhook` service runs on Render's free tier, which has
ephemeral storage and sleeps when idle — a poor fit for a durable spend counter
that must survive restarts and reliably enforce a monthly cap. Cloudflare
Workers don't cold-start/sleep the same way, and Workers KV gives durable,
free-tier storage for the counter. Trade-off: a second hosting provider to
manage (vs. consolidating on Render). Accepted for the better fit and zero
ongoing cost at trial scale.

## Trial limits

Two independent caps:

### Per-install (local, advisory)

- A simple integer counter in `core/config.py` (same storage the LAN-sync token
  and prefs already use). Starts at 10, decrements only on a **confirmed
  successful** identification.
- Trivially resettable (delete config / reinstall). **This is fine and
  intentional.** Nobody will uninstall → reinstall → re-provision the app to
  reclaim 10 identifications worth ~6 cents. The per-install counter's only job
  is light friction so a casual user doesn't farm free scans by clearing
  config; it is **not** a security boundary.
- No server-side per-install tracking, no device ID, no fingerprint — that
  would undercut the "nothing tracked" pitch for negligible benefit.

### Global monthly cap (server, enforced)

- The Worker enforces a hard monthly identification-count ceiling
  (`MONTHLY_TRIAL_CAP`, a Worker binding the developer sets), backed by a KV
  counter keyed by month (e.g. `trial:2026-07`).
- **Budget: $100/month worst-case spend**, expressed to the Worker as an
  identification-count ceiling: at ~$0.006/identification that's ~16,600
  identifications/month (`MONTHLY_TRIAL_CAP ≈ 16600`). Adjustable via the Worker
  binding without a redeploy of the desktop app. Because the cap is derived from
  a dollar budget, revisit the count if Anthropic's per-identification cost
  changes.
- This is the **real** backstop and the thing that actually bounds developer
  spend. The threat it defends against is not a human reinstalling the app —
  it's someone scripting the Worker endpoint directly in a loop, bypassing the
  app entirely.
- When the cap is hit, the Worker refuses **all** trial requests until the
  month rolls over. BYO-key users are unaffected (they never hit the Worker).

## Abuse model

| Vector | Mitigation |
|--------|-----------|
| Human uninstalls/reinstalls to farm trials | Ignored — effort vastly exceeds ~$0.06 of value. |
| Casual user clears local config | Ignored — same reason; local counter is advisory only. |
| Scripted/looped calls to the Worker endpoint | **Global monthly KV cap** — hard ceiling on total spend regardless of source. |

The local counter is never trusted for enforcement — only for deciding when to
show the upgrade dialog. Spend is bounded server-side.

## Components

### 1. Cloudflare Worker (`trial-proxy/`, new)

- **Endpoint:** `POST /v1/identify` (single purpose: relay one card
  identification).
- **Behavior:**
  1. Read the current month's KV counter.
  2. If counter ≥ `MONTHLY_TRIAL_CAP` → return `429` with a distinct
     machine-readable reason (`{"error":"trial_capacity"}`).
  3. Otherwise inject the developer's Anthropic key, forward the vision request
     to the Anthropic API, stream/return the response.
  4. On a confirmed Anthropic success, increment the KV counter.
- **Zero logging of payloads.** The Worker relays request → response and
  persists nothing except the monthly integer. No card images, no responses,
  no IP-linked records. This keeps "we don't store your cards" true even during
  the trial.
- **Config:** `ANTHROPIC_API_KEY` (dev's key) and `MONTHLY_TRIAL_CAP` as Worker
  secrets/vars. KV namespace bound for the counter.

### 2. Desktop routing (`core/identifier.py`, modified)

The one place that calls Claude vision. New three-way decision:

1. Own `ANTHROPIC_API_KEY` present → call Anthropic **directly** (unchanged).
2. No own key, trial count > 0 → route through the **Worker**; decrement the
   local counter only on confirmed success.
3. No own key, trial count == 0 → raise a `TrialExhausted` state (no network
   call) that triggers the upgrade dialog.

The bundled Worker URL is a hardcoded constant in the shipped app so the trial
works out-of-the-box with zero config.

### 3. Streamlined key dialog (`ui/`, new — reused in two places)

Compact dialog with three actions:

- **Get a key** → opens the browser deep-linked straight to
  `https://console.anthropic.com/settings/keys` (not the homepage). Dialog
  stays open behind it.
- **Paste key** → inline text field; on paste, validate immediately with a
  lightweight Anthropic ping (e.g. a minimal `/v1/models` call or tiny test
  request) → green ✓ or a clear error *before* closing. On success, save via
  the existing `config.apply_to_env` path and close.
- **Maybe later** → dismiss; app remains usable for manual scan + type-in
  (consistent with today's "skip is allowed").

This **same** dialog replaces the current first-run key prompt, so BYO-key
onboarding is smoother for everyone — one code path, whether hit on day one or
at trial exhaustion.

### 4. First-run reordering (`ui/main_window.py`, modified)

- Keep the welcome notice (`_show_first_run_notice` — good tone-setter).
- **Delete `_prompt_for_keys_if_needed()` entirely.** New users land on a
  working app with 10 free scans available; the scan button just works.
- The key ask now surfaces **only** at trial exhaustion (component 3), after
  the user has already gotten value.

### 5. Trial-exhausted trigger

When a scan is attempted with trial count == 0 (component 2, case 3), show the
streamlined dialog (component 3) with trial-specific copy:

> "You've used your 10 free card identifications. To keep scanning, add your
> own free Anthropic key — it's about $0.006 per card."

## Failure handling

Each new failure mode gets a distinct, honest message. A credit is consumed
**only** on confirmed success — never on a failed call.

| Condition | Message | Credit? |
|-----------|---------|---------|
| Worker unreachable / offline | "Free trial service is temporarily unavailable. You can add your own key to keep scanning, or try again later." | Not consumed |
| Global cap hit (Worker `429 trial_capacity`) | "The free trial is at capacity right now. Add your own key to keep scanning." | Not consumed |
| Anthropic error passed through (rate limit, model error) | Surface as today. | Not consumed |
| Success | — | Decrement local counter |

Fail-open to BYO-key: any trial failure points the user at the "add your own
key" path rather than dead-ending.

## Privacy reconciliation

The site currently says "nothing is uploaded to us." The trial makes that
conditional, so the claim must be refined, not dropped:

- **BYO-key scans** still go direct to Anthropic — nothing uploaded to the
  developer. The absolute claim stays true for these users.
- **Trial scans** relay a card image through the developer's Worker to
  Anthropic. The Worker **stores nothing** (only a monthly integer), so "we
  don't *store* your cards" remains true even during trial.
- **In-app disclosure** at the trial dialog, at the moment it's relevant:
  > "During the free trial, card images are sent through LoreBox's server to
  > identify them. Add your own key and scanning goes directly to Anthropic —
  > nothing passes through us."
- **Site / PRIVACY.md** update to distinguish trial (relayed, not stored) from
  BYO-key (direct). Treated as a **separate reviewable change**, not bundled
  silently into the code change. Exact lines to be flagged during
  implementation.

Keeping the Worker strictly zero-logging is what preserves the privacy story.

## Testing

Consistent with the existing `tests/` pytest pattern; no live API calls (mock
the Worker and Anthropic endpoints, as the sync tests stub things).

**Worker:**
- Under cap → forwards and increments.
- At/over cap → `429 trial_capacity`, does not forward.
- Missing/blank body → `400`.
- Never logs image payloads.

**Desktop routing (`identifier.py`):**
- Own key → direct call, Worker not invoked.
- No key, trial > 0 → routed through Worker.
- No key, trial == 0 → raises `TrialExhausted`, no network call.
- Failed proxy call does **not** decrement the counter.

## Open items / follow-ups

- `MONTHLY_TRIAL_CAP` derived from a **$100/month** budget (~16,600
  identifications at ~$0.006 each). This comfortably covers ~1,600 users each
  consuming a full 10-scan trial per month before the global cap bites — ample
  headroom at expected scale. Re-derive the count if per-identification cost
  changes, and monitor actual monthly spend against the $100 target.
- Consider a Cloudflare billing alert / Anthropic usage alert as a secondary
  safety net independent of the KV counter.
- PRIVACY.md + site copy edits — separate change, flagged during implementation.
- Bundled Worker URL constant — final production URL set once the Worker is
  deployed.

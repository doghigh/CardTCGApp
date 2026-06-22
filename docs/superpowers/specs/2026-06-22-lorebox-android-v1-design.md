# LoreBox Android (v1) — Design

**Date:** 2026-06-22
**Author:** Jesse (with Claude)
**Status:** Approved for planning

## Summary

A native Android app for LoreBox that works **fully standalone**: capture a trading
card with the phone camera → identify it with Claude vision → fetch a market value →
save it to a local, searchable collection. It mirrors the existing Windows desktop
app's data model exactly so a later LAN-sync feature drops in cleanly.

The app is a **companion when a PC is present** (one-time QR key provisioning from the
desktop; live LAN sync is a later spec) and a **standalone main app when it is not**.

### Guiding principles (carried from desktop)

- **Privacy-first:** no account, no analytics, no cloud. Collection data stays on the device.
- **Official APIs only:** Scryfall (Magic) and eBay Browse API. No web scraping.
- **Bring-your-own-key:** the user's own Anthropic/eBay keys power identify and non-Magic
  valuation. Magic cards work with **zero keys** (Scryfall is free/keyless).

## Scope

### In scope (v1)

- CameraX capture of card front (and optional back).
- Card identification via the Anthropic Messages API (`claude-haiku-4-5-20251001`),
  reusing the desktop's exact vision prompt and JSON output shape.
- Valuation: Scryfall for Magic (keyless), eBay Browse API for everything else
  (OAuth client-credentials, same median/trim/0.85-discount logic as desktop).
- Local collection in Room (SQLite) with search, card detail, edit, and delete.
- Duplicate merge on save (name + set + number + game + foil → bump quantity).
- Settings: API keys, optional biometric/PIN app-lock.
- **QR key provisioning:** a new "Pair phone" dialog on the *desktop* app renders a
  QR containing the user's keys; the phone's first-run setup scans it and stores the
  keys encrypted. Manual key entry is the fallback.

### Out of scope (each a later spec)

- Condition grading (OpenCV port). Schema columns exist but stay null in v1.
- Live LAN sync of the collection between phone and PC.
- Epson scanner SDK integration.
- PDF reports and dashboard charts.
- iOS.

## Architecture

Modern Android: **Kotlin + Jetpack Compose, MVVM**, single Gradle module to start,
living in `/android` on the `android-app` branch of this repo.

### Layers

- **UI (Compose):**
  - `CaptureScreen` — CameraX preview; capture front, then optional back.
  - `ReviewScreen` — shows identified fields + fetched value; all fields editable before save.
  - `CollectionScreen` — searchable list of saved cards.
  - `CardDetailScreen` — full card view; edit / delete.
  - `SettingsScreen` — API keys, app-lock toggle, QR pairing entry point.
  - `Onboarding/PairScreen` — first-run: scan desktop QR or enter keys manually.
  - Navigation via Compose Navigation.
- **ViewModel:** one per screen, exposes `StateFlow<UiState>`; holds no Android
  framework types beyond what AndroidViewModel requires.
- **Data:**
  - `CardRepository` over **Room**. Orchestrates the identify → value → save pipeline
    so ViewModels stay thin.
  - `IdentifyService` — Anthropic Messages API client (Retrofit/OkHttp + kotlinx-serialization).
  - `ValuationService` — Scryfall + eBay Browse clients with OAuth token cache.
  - `KeyStore` wrapper over EncryptedSharedPreferences (Android Keystore-backed).
  - `ImageStore` — saves captured JPEGs to app-internal `filesDir`; returns paths.

All network and DB work runs on Kotlin coroutines.

### Data flow (capture → save)

1. `CaptureScreen` saves front/back JPEGs via `ImageStore`, returns file paths.
2. `ReviewViewModel` calls `CardRepository.identifyAndValue(frontPath, backPath?)`.
3. Repository: `IdentifyService.identify(...)` → card fields; then
   `ValuationService.value(name, set, game)` → estimated value.
4. `ReviewScreen` shows the result; user edits if needed and confirms.
5. Repository `addCard(...)` applies the duplicate-merge rule and writes to Room.

## Data model (Room)

`CardEntity` mirrors the desktop `cards` table column-for-column (Kotlin camelCase
names map to the same concepts):

```
id, name, setName, cardNumber, rarity, game, year, language, foil,
frontScanPath, backScanPath, conditionGrade, conditionScore, defectsJson,
estimatedValue, purchasePrice, purchaseDate, notes, quantity, createdAt, updatedAt
```

- Grading columns (`conditionGrade`, `conditionScore`, `defectsJson`) exist but stay
  null in v1 so the grading spec needs no migration.
- `ValuationEntity` mirrors the desktop `valuations` table
  (`id, cardId, source, value, currency, url, fetchedAt`).
- **Duplicate merge:** match on `name` (case-insensitive) + `setName` + `cardNumber`
  + `game` + `foil`; on match, increment `quantity` rather than inserting.
- Field validation mirrors `database._validate_card` (length caps, year range,
  non-negative prices, foil as 0/1).

Keeping the schema identical to desktop is what makes future LAN sync a
data-mapping exercise rather than a redesign.

## Identification

- Endpoint: Anthropic Messages API, model `claude-haiku-4-5-20251001`, `max_tokens=256`.
- Prompt: the **exact `VISION_PROMPT`** from `core/identifier.py` (same field
  definitions, same MTG title-bar guidance, same example).
- Images: front (and back if captured) as base64 JPEG, downscaled so the longest
  edge ≤ 1600px, quality 85 — matching desktop.
- Output: JSON with `name, set_name, card_number, rarity, year, game`. Apply the same
  defensive cleanup (never let a game name leak into `set_name`).
- No on-device OCR fallback in v1: if identify fails or no key is set, the user enters
  fields manually on `ReviewScreen`. (Tesseract fallback can be a later add.)

## Valuation

Ported from `core/valuator.py`:

- **Magic:** Scryfall `/cards/named` (fuzzy + set code), with `/cards/search` fallback
  ordered by ascending USD. Keyless. Respect ~120ms throttle.
- **Everything else:** eBay Browse API. OAuth client-credentials token (cached, 5-min
  early expiry). Query built from name + set + game keyword + "card". Median of the
  10%-trimmed price list, then **× 0.85** (active listings sell below asking).
- Category mapping: sports → `213`, CCG → `183454`, non-sport/unknown → no category.
- Condition multipliers table retained for when grading lands; v1 uses the default
  (no grade → multiplier 1.0-ish via `condition_score / 85`).

## API keys & provisioning

- Keys stored in **EncryptedSharedPreferences** (Android Keystore-backed).
- **QR provisioning (primary):** desktop "Pair phone" dialog renders a QR encoding a
  small JSON payload `{ anthropicKey, ebayAppId, ebayCertId, ... }`. Phone first-run
  scans it (CameraX + ML Kit/ZXing barcode) and persists the keys. The QR is shown on
  the user's own PC and scanned by their own phone; nothing transits a network.
- **Manual entry (fallback):** Settings lets the user paste keys directly (no-PC case).
- Magic-card identify needs no eBay key; Magic valuation needs no key at all, so the
  app is useful immediately for MTG and lights up further as keys are added.

### Desktop-side change

A new `ui/pair_dialog.py` (PyQt6) renders the QR from existing config keys using the
already-present `qrcode` dependency. This is the only desktop change in v1.

## Auth

Optional **biometric/PIN app-lock** via AndroidX `BiometricPrompt`, **off by default**
(parity with desktop's optional Windows Hello/TOTP; never blocks first use).

## Error handling

- No/invalid API key → identify/eBay calls short-circuit with a clear message; user
  falls back to manual entry. Magic valuation still works.
- Network failure → surfaced as a retryable error on `ReviewScreen`; the user can still
  save with manually entered data.
- Camera permission denied → explanatory screen with a settings deep-link.
- Malformed identify JSON → treat as "not identified"; manual entry path.

## Testing

- **Unit (JUnit):** valuation parsing (Scryfall result, eBay median/trim/discount),
  identify JSON parsing + defensive cleanup, duplicate-merge key logic, field validation.
- **Room (instrumented):** insert, dedupe-merge, search queries.
- **Repository:** identify → value → save pipeline with fake `IdentifyService` /
  `ValuationService`.
- CameraX and Compose screens verified manually for v1; automated UI tests deferred.

## Repo & branching

- Branch `android-app` off `main` in this repo.
- App under `/android` (standard Gradle project).
- `main` stays untouched and Store-shippable until v1 is merged.
- Shared schema lives in one repo, preventing desktop/Android drift.

## Follow-up specs (not v1)

1. Condition grading (OpenCV on-device).
2. Live LAN sync (desktop receiver + phone push).
3. Epson scanner SDK capture.
4. Reports & dashboard.

# LoreBox LAN Sync (v1) — Design

**Date:** 2026-06-26
**Author:** Jesse (with Claude)
**Status:** Approved for planning
**Repos:** spans **LoreBox-Mobile** (Android, phone side) and **CardTCGApp** (desktop, receiver side)

## Summary

Let the phone push the cards it has scanned to the desktop app over the local
network (WiFi), so the desktop remains the master collection ("library of
record") while the phone stays a lightweight capture device. The phone holds
**only the cards it has scanned and not yet offloaded**; syncing **moves** a card
from phone to PC and frees the phone's storage.

This builds directly on the v1 decisions: the PC runs a small local server and
the phone pushes to it; the QR pairing infrastructure already on both sides is
reused to establish the connection.

### Mental model

- **No PC:** scanned cards accumulate on the phone — that *is* the collection (standalone use).
- **PC present:** the user multi-selects scanned cards and pushes them to the PC.
  Each card the PC acknowledges is **deleted from the phone** (row + scan images).
  The phone never grows into a full library.

Because a card lives in exactly one place and sync *moves* it (not copies it),
there is no idempotency/double-count problem and no conflict resolution.

## Scope

### In scope (v1)

- **Phone → PC, one direction only.** No PC → phone.
- **User-selected push:** multi-select cards on the phone, push to the PC.
- **Per-card acknowledgement:** each card the PC confirms is deleted from the phone
  (Room row + front/back JPEGs). A partial failure leaves un-acked cards on the phone for retry.
- **QR connect:** desktop "Receive from phone" mode starts the server and shows a QR
  with the PC's current LAN IP + port + sync token; the phone scans it (reusing the
  existing ZXing scanner). The phone remembers the host for routine syncs; re-scans
  only if the connection fails (IP changed).
- **Bearer-token auth over plain HTTP on the LAN** (no TLS).
- **Server runs only while the "Receive from phone" dialog is open.**
- **PC merges received cards** into its collection via the existing
  `add_card(merge_duplicates=True)`; received images saved to the desktop's scans dir.

### Out of scope (later specs)

- Two-way / bidirectional sync; editing or deleting on the PC propagating to the phone.
- mDNS/NSD zero-config discovery.
- Off-network / cloud relay sync.
- Re-valuation on the PC (the PC stores the value the phone already computed; the
  user can re-value later via existing desktop UI).

## Architecture

Three units with one clear responsibility each:

1. **Desktop sync server** (`CardTCGApp`) — a small Flask app on a background thread,
   bound to `0.0.0.0:<port>`, token-gated, that ingests cards and images into the
   existing `Database`. Lifecycle owned by the receive dialog.
2. **Desktop receive UI** (`CardTCGApp`) — a "Receive from phone" dialog that starts/stops
   the server, renders the connection QR, and shows a live "received N cards" log.
3. **Phone sync client** (`LoreBox-Mobile`) — selection UI + a `SyncClient` that pushes
   selected cards card-by-card and deletes each on ack, plus connection management
   (stored host, ping check, re-scan on failure).

### The sync protocol (shared contract — lives in both repos)

Base URL `http://<host>:<port>`. Every request carries `Authorization: Bearer <syncToken>`.
The server rejects missing/invalid tokens with `401` (constant-time compare).

- **`GET /sync/ping`** → `200 {"app":"lorebox","proto":1}`. Used right after a QR scan
  (and before each sync session) to verify the host is reachable and the token is valid.
- **`POST /sync/card`** — one card per request, `multipart/form-data`:
  - part `meta` (application/json): the card fields mirroring the schema —
    `name, set_name, card_number, rarity, game, year, language, foil,
    condition_grade, condition_score, defects_json, estimated_value,
    purchase_price, purchase_date, notes, quantity`.
  - part `front` (image/jpeg): required.
  - part `back` (image/jpeg): optional.
  - Server: validate token → save image(s) to the desktop scans dir → call
    `db.add_card({...meta, front_scan_path, back_scan_path}, merge_duplicates=True)`
    → return `200 {"id": <card_id>}` (the ack). On error return `4xx/5xx` with a message.

One card per request gives natural per-card acks and partial-failure resilience:
the phone deletes a card only when it sees that card's `200`.

### QR connection payload

A JSON object encoded in the desktop QR and scanned by the phone:

```json
{ "host": "192.168.1.42", "port": 8765, "syncToken": "<32+ char random>" }
```

The phone stores `host`, `port`, `syncToken` in its encrypted `KeyStore` for reuse.
(This is a distinct payload type from the existing key-provisioning QR; the phone's
scan handler distinguishes them by shape.)

## Data flow (select → push → ack → delete)

1. Desktop: user opens **Receive from phone** → server starts → QR shown (current LAN IP+port+token).
2. Phone: user multi-selects scanned cards → **Sync to PC**.
3. Phone: connection check — if a stored host exists, `GET /sync/ping`; if it fails,
   prompt to scan the desktop QR, store host+token, retry ping.
4. Phone: for each selected card, `POST /sync/card` (meta + image bytes).
5. Desktop: ingest → `add_card(merge_duplicates=True)` → save images → respond `200 {id}`,
   and append to the dialog's live log.
6. Phone: on each `200`, delete that card locally (Room row + its JPEG files via the repository),
   update progress ("3/10 synced"). On a non-200/timeout, leave the card and mark it failed
   (retryable).
7. When the user closes the desktop dialog, the server stops.

## Merge semantics (PC side)

The PC uses the existing duplicate key (name + set + number + game + foil). A pushed
card that matches an existing printing **increments quantity** — which is correct here,
since the phone is sending another physical copy. New printings insert a new row. This
reuses `Database.add_card`/`find_duplicate` unchanged.

## Security

- **Bearer token** (random ≥32 chars) generated once on the desktop, stored in the
  encrypted desktop config (`config.enc`), embedded in the QR, reused across sessions.
  Server compares with a constant-time check; `401` on mismatch.
- **Plain HTTP on the LAN** — no TLS. Rationale: card data + scan images are not secret,
  never leave the local network, and the token blocks other LAN devices; self-signed TLS
  on a bare IP adds trust-prompt pain for no real gain.
- **Bounded exposure:** the server listens **only while the receive dialog is open**.
  No always-on background listener.

## Error handling

- **Bad/missing token →** `401`; phone shows "Not authorized — re-scan the desktop QR".
- **Host unreachable / IP changed →** ping fails; phone prompts to re-scan the QR.
- **Per-card failure (timeout, 5xx, bad image) →** that card stays on the phone, marked
  failed in the selection; the rest continue; user retries failed ones.
- **Image save fails on PC →** server returns an error for that card; phone does not delete it.
- **App/dialog closed mid-sync →** server stops; in-flight card not acked → stays on phone.
- **Duplicate delivery** (phone retried a card the PC already stored but the ack was lost):
  acceptable edge — `merge_duplicates` would bump quantity by one extra. Mitigation:
  include a per-card `client_uid` (random, stored on the phone card) in `meta`; the server
  keeps a short-lived set of seen `client_uid`s for the session and treats a repeat as an
  idempotent ack (returns the same id without re-adding).

## Testing

**Phone (`LoreBox-Mobile`)**
- `SyncClient` unit tests with a fake HTTP server: request shape (multipart parts, bearer
  header), `200` → returns id, non-200/timeout → failure; delete-on-ack invoked only on success.
- Selection-state logic: selected set, remove-on-ack, failed-stay-selectable.
- Connection logic: stored host → ping ok path; ping fail → re-scan required.

**Desktop (`CardTCGApp`)**
- Server endpoint tests (Flask test client): `401` without/with-wrong token; `/sync/ping` ok;
  `/sync/card` calls `add_card(merge_duplicates=True)` with the right dict, saves images, returns id;
  duplicate `client_uid` is idempotent.
- LAN IP detection util; constant-time token compare; QR payload builder.

**End-to-end (manual):** desktop receive mode + phone push of a multi-card selection on the
real device; verify cards land/merge on the PC, images render, and synced cards vanish from the phone.

## Repo split

**Desktop — `CardTCGApp`:**
- `core/sync_server.py` — Flask app + background-thread lifecycle + token auth + card/image ingest.
- `core/net_utils.py` (or similar) — LAN IP detection.
- `ui/sync_receive_dialog.py` — "Receive from phone" dialog: start/stop server, render QR
  (reuse `pair_dialog`'s QR rendering), live received-cards log.
- `core/config.py` — add/generate the persistent `sync_token`.
- `ui/main_window.py` — "Receive from phone…" action.

**Phone — `LoreBox-Mobile`:**
- `data/sync/SyncClient.kt` — OkHttp multipart push, ping, per-card ack.
- `data/sync/SyncEndpoint.kt` — QR payload model (host/port/token) + parse; stored in `KeyStore`.
- Collection screen — multi-select mode + "Sync to PC" action + progress UI.
- Reuse the existing ZXing scanner for the connection QR (distinguish payload type).
- `CardRepository` — a `deleteCard` path that removes the row **and** its scan-image files.

**Shared contract:** the protocol + QR payload (this spec's two sections) kept in both repos'
docs so phone and desktop can't drift.

## Follow-up specs (not v1)

1. Two-way sync (PC → phone; edits/deletes; conflict resolution).
2. mDNS/NSD zero-config discovery (drop the QR step for repeat syncs).
3. Background/always-available receive mode if desired.
4. **"Storage saver" image compression** (standalone-only concern, considered and
   deferred). For a phone used *without* a PC, scanned cards accumulate and their
   images consume storage. A later setting could downsize a card's stored image to a
   display thumbnail (~700px / q70) **after all detail-dependent analysis is done**.
   Crucially this must run only after **grading** (a planned feature needing
   corner/edge/surface detail) — compressing right after identify+value would
   irreversibly destroy detail a future grade pass needs. Deferred because: images are
   already downscaled at capture (≤1600px/q85, ~200–400 KB), LAN sync is the primary
   memory strategy, and the correct compression threshold depends on grading existing.

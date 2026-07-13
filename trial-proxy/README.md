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

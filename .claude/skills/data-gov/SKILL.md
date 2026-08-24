---
name: data-gov
description: >-
  Query U.S. government open data through api.data.gov, the shared API gateway
  that fronts federal agency APIs (NASA, USDA FoodData Central, College
  Scorecard, NREL energy data, Regulations.gov, FEC, GovInfo, and more) with a
  single API key. Use this skill whenever the user wants federal/government
  data, mentions data.gov, api.data.gov, a "DEMO_KEY", or names one of the
  agency APIs above — including tasks like "look up nutrition facts for a food",
  "find colleges by graduation rate", "get today's NASA astronomy photo",
  "search federal regulations", or "search the data.gov catalog for datasets".
  Also use it when someone hits an API_KEY_* or OVER_RATE_LIMIT error from a
  federal API, or asks how to authenticate/rate-limit against api.data.gov.
---

# data.gov API

`api.data.gov` is not a data source itself — it is a lightweight **API
management gateway** (built on api-umbrella) that the U.S. government puts in
front of many agency APIs. It gives you three things across every participating
API: a single shared **API key**, consistent **rate limiting**, and uniform
**analytics/error handling**. Learn it once and it works for NASA, USDA,
Department of Education, NREL, and dozens more.

Two distinct things are commonly called "data.gov" — know which one the user
means:

1. **api.data.gov** — the API *gateway* (this skill's main focus). Requests go
   to agency hosts like `api.nasa.gov` or `api.nal.usda.gov`, authenticated
   with a data.gov key. Covered below and in `references/participating-apis.md`.
2. **catalog.data.gov** — the dataset *catalog*, a CKAN instance listing
   ~250k+ datasets. Its search API is **separate** and needs **no key**. Use it
   to discover datasets. Covered in `references/catalog-ckan.md`.

If the user wants to *call a specific federal API*, use path 1. If they want to
*discover what datasets exist*, use path 2. When in doubt, catalog search is the
safe starting point because it requires no credentials.

## Getting and using an API key

- **Sign up** (free, instant, email-verified): https://api.data.gov/signup/
- **`DEMO_KEY`** — a shared key for quick exploration with no signup. It is
  heavily throttled (about **30 requests/hour** and **50 requests/day** per IP),
  so use it only for a first sanity-check, never in real workflows or loops.
- Store a real key in the `DATA_GOV_API_KEY` environment variable rather than
  hardcoding it. Treat it like a password — it identifies the caller and counts
  against a rate limit, so keep it out of committed code, logs, and URLs you
  share.

Pass the key one of three ways (pick the header form — it keeps the key out of
URLs, server logs, and browser history):

```bash
# 1. HTTP header (preferred)
curl -H "X-Api-Key: $DATA_GOV_API_KEY" "https://api.nasa.gov/planetary/apod"

# 2. Query-string parameter (fine for quick tests; leaks into logs/history)
curl "https://api.nasa.gov/planetary/apod?api_key=$DATA_GOV_API_KEY"

# 3. HTTP Basic auth, key as the username (used by a few APIs)
curl -u "$DATA_GOV_API_KEY:" "https://api.nasa.gov/planetary/apod"
```

All requests must use **HTTPS** — plain HTTP is rejected with an
`HTTPS_REQUIRED` error.

## Rate limits

The default limit is **1,000 requests/hour per key** (some APIs set their own —
NASA is also 1,000/hour; check each API's docs). Every response carries the
current budget in headers, so read them instead of guessing:

- `X-RateLimit-Limit` — total requests allowed in the window
- `X-RateLimit-Remaining` — requests left in the current window

When you exceed the limit you get **HTTP 429** with error code
`OVER_RATE_LIMIT`. The right response is to back off (the window is hourly), not
to retry in a tight loop. If a legitimate workload needs a higher ceiling,
the fix is to email the address in the manual to request an increase — not to
rotate through multiple keys.

## Error handling

Errors come back as JSON with an `error` object (or a top-level `errors` array,
depending on the API). Map the `code` to a cause before retrying — most of these
are permanent for the current request and retrying unchanged just burns budget:

| code | meaning | what to do |
| --- | --- | --- |
| `API_KEY_MISSING` | no key sent | add the `X-Api-Key` header |
| `API_KEY_INVALID` | key not recognized | check for typos / wrong env var |
| `API_KEY_DISABLED` | key was disabled | sign up for a new key |
| `API_KEY_UNAUTHORIZED` | key lacks access to this API | some APIs require separate enrollment |
| `API_KEY_UNVERIFIED` | email not confirmed | click the verification link from signup |
| `HTTPS_REQUIRED` | request used plain HTTP | switch the URL to `https://` |
| `OVER_RATE_LIMIT` | 429, hourly budget spent | back off until the window resets |
| `NOT_FOUND` | bad path/resource | fix the endpoint path |

## The connector (recommended way to call it)

This repo ships an MCP connector at `connectors/data-gov-mcp/` that wraps all of
the above: it injects the key from `DATA_GOV_API_KEY`, always uses the header
form and HTTPS, surfaces the rate-limit headers, and decodes the error codes.
Prefer its tools over hand-rolling `curl`:

- `datagov_request` — authenticated GET to **any** api.data.gov-managed URL or
  path; the escape hatch for APIs without a dedicated tool.
- `catalog_search` / `catalog_package_show` — discover datasets in the CKAN
  catalog (no key needed).
- Curated convenience tools: `nasa_apod`, `college_scorecard_search`,
  `fooddata_search`, `nrel_utility_rates`.

See `connectors/data-gov-mcp/README.md` for setup. If the connector is not
available in the current session, fall back to `curl`/`requests` using the
patterns above.

## Choosing an approach

1. **Discovery** ("what data exists about X?") → `catalog_search` (CKAN, no key).
2. **A specific known agency API** → the curated tool if one exists, else
   `datagov_request` with the agency's base URL and path.
3. **Just teaching/authentication questions** → answer from this file directly.

## Reference files

Read these as needed — don't load them all up front:

- `references/participating-apis.md` — base URLs, endpoints, and example
  requests for the popular agency APIs (NASA, FoodData Central, College
  Scorecard, NREL, Regulations.gov, FEC, GovInfo). Read when the user names a
  specific agency/dataset and you need its exact URL and parameters.
- `references/catalog-ckan.md` — the catalog.data.gov CKAN Action API
  (`package_search`, `package_show`, `organization_list`, etc.). Read when the
  task is dataset discovery rather than calling a specific API.

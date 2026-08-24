# catalog.data.gov (CKAN Action API)

This is the **dataset catalog**, distinct from the `api.data.gov` gateway. It is
a standard [CKAN](https://docs.ckan.org/en/latest/api/) instance, so it speaks
the CKAN **Action API**. It needs **no API key** — anyone can query it.

Use it to answer "what datasets exist about X, and who publishes them?" Then, if
a dataset exposes its own API, call that API (via the gateway if it's
data.gov-managed).

Base: `https://catalog.data.gov/api/3/action`

Every action is `GET https://catalog.data.gov/api/3/action/{action}?{params}`
(some also accept POST with a JSON body). Responses have the shape:

```json
{ "success": true, "result": { ... } }
```

Check `success` before reading `result`. On failure, `error` explains why.

## Most useful actions

| Action | Purpose | Key params |
| --- | --- | --- |
| `package_search` | Full-text + faceted dataset search | `q`, `rows` (default 10, max 1000), `start` (offset), `fq` (filter query), `sort`, `facet.field` |
| `package_show` | Full metadata for one dataset, including its resources/distributions | `id` (dataset name or UUID) |
| `resource_search` | Search individual resources (files/endpoints) | `query` e.g. `name:data`, `format` |
| `organization_list` | List publishing organizations (agencies) | `all_fields=true`, `limit` |
| `organization_show` | One organization + its datasets | `id`, `include_datasets=true` |
| `group_list` / `tag_list` | Topic groups / tags | `all_fields`, `query` |

## Searching

```bash
# Free-text search
curl "https://catalog.data.gov/api/3/action/package_search?q=wildfire&rows=5"

# Filter by publishing org and format, newest first
curl "https://catalog.data.gov/api/3/action/package_search?q=air+quality&fq=organization:epa-gov&sort=metadata_modified+desc&rows=5"

# Faceted counts (how many datasets per organization)
curl "https://catalog.data.gov/api/3/action/package_search?q=climate&facet.field=[\"organization\"]&rows=0"
```

`package_search` result fields worth knowing:

- `result.count` — total matches (use with `start` to paginate)
- `result.results[]` — the datasets. Each has `title`, `name` (slug id),
  `notes` (description), `organization.title`, `tags[]`, and `resources[]`.
- Each `resources[]` entry has `url`, `format` (CSV, JSON, API, ...), `name`,
  and `description` — this is where the actual data/endpoint lives.

## From a dataset to its data

1. `package_search?q=...` → pick a dataset, note its `name`.
2. `package_show?id={name}` → read `resources[]`.
3. If a resource `format` is `API` (or the `url` is a live endpoint), call it.
   If it's data.gov-managed, route through the gateway with the data.gov key;
   otherwise call it directly.

## Filter-query (`fq`) cheatsheet

`fq` uses Solr syntax. Combine with `+` (AND) / `-` (NOT):

- `organization:noaa-gov` — by publishing org slug
- `res_format:CSV` — datasets having a CSV resource
- `tags:earthquake` — by tag
- `groups:climate5434` — by topic group

Example: `fq=organization:census-gov+res_format:JSON`

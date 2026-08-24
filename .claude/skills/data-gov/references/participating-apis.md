# Participating agency APIs (api.data.gov)

Every API below is fronted by `api.data.gov`, so the **same data.gov key** and
the auth/rate-limit rules from `SKILL.md` apply. Send the key as
`X-Api-Key: $DATA_GOV_API_KEY` and always use HTTPS.

This is a curated subset of the most-requested APIs. The full, current roster
lives at https://api.data.gov (the developer manual links each agency's own
docs). When an API isn't listed here, use the connector's `datagov_request`
tool with the agency base URL + path from the agency's own documentation.

## Table of contents

- [NASA](#nasa)
- [USDA FoodData Central](#usda-fooddata-central)
- [College Scorecard (Dept. of Education)](#college-scorecard-dept-of-education)
- [NREL (National Renewable Energy Laboratory)](#nrel-national-renewable-energy-laboratory)
- [Regulations.gov](#regulationsgov)
- [FEC (Federal Election Commission)](#fec-federal-election-commission)
- [GovInfo](#govinfo)

---

## NASA

Base: `https://api.nasa.gov`

| Endpoint | Purpose |
| --- | --- |
| `GET /planetary/apod` | Astronomy Picture of the Day. Params: `date` (YYYY-MM-DD), `start_date`+`end_date` for a range, `thumbs`. |
| `GET /neo/rest/v1/feed` | Near-Earth Objects. Params: `start_date`, `end_date` (max 7-day span). |
| `GET /mars-photos/api/v1/rovers/{rover}/photos` | Mars rover photos. Params: `sol` or `earth_date`, `camera`, `page`. Rovers: `curiosity`, `opportunity`, `spirit`, `perseverance`. |
| `GET /EPIC/api/natural` | Earth polychromatic imaging (DSCOVR). |
| `GET /DONKI/...` | Space weather (CME, solar flares, geomagnetic storms). |

```bash
curl -H "X-Api-Key: $DATA_GOV_API_KEY" \
  "https://api.nasa.gov/planetary/apod?date=2024-07-04"
```

NASA also accepts `DEMO_KEY`, which is handy for a one-off test.

## USDA FoodData Central

Base: `https://api.nal.usda.gov/fdc/v1`

| Endpoint | Purpose |
| --- | --- |
| `GET /foods/search` | Search foods. Params: `query`, `dataType` (e.g. `Foundation,SR Legacy,Branded`), `pageSize`, `pageNumber`. |
| `GET /food/{fdcId}` | Full nutrient detail for one food. Params: `format` (`abridged`/`full`), `nutrients`. |
| `POST /foods` | Batch fetch multiple `fdcIds`. |

```bash
curl -H "X-Api-Key: $DATA_GOV_API_KEY" \
  "https://api.nal.usda.gov/fdc/v1/foods/search?query=cheddar%20cheese&pageSize=5"
```

Nutrient amounts are in `foodNutrients[]`; each has `nutrientName`,
`unitName`, and `value`. Energy (kcal) is usually `nutrientName == "Energy"`.

## College Scorecard (Dept. of Education)

Base: `https://api.data.gov/ed/collegescorecard/v1`

| Endpoint | Purpose |
| --- | --- |
| `GET /schools` | Search/filter institutions. |

Uses dotted field names and `.` operators. Key params:

- `school.name`, `school.state`, `school.city`
- `latest.admissions.admission_rate.overall__range=0..0.2` (range filter)
- `latest.student.size__range`, `latest.cost.tuition.in_state`
- `fields=` — **always set this**; responses are huge otherwise. Comma-separated
  list, e.g. `fields=id,school.name,school.state,latest.admissions.admission_rate.overall`
- `sort=latest.student.size:desc`, `per_page` (max 100), `page`

```bash
curl -H "X-Api-Key: $DATA_GOV_API_KEY" \
  "https://api.data.gov/ed/collegescorecard/v1/schools?school.state=CA&fields=id,school.name,latest.student.size&per_page=5"
```

Results are under `results[]`; pagination info under `metadata`.

## NREL (National Renewable Energy Laboratory)

Base: `https://developer.nrel.gov`

| Endpoint | Purpose |
| --- | --- |
| `GET /api/utility_rates/v3.json` | Average commercial/residential/industrial electricity rates. Params: `lat`, `lon`. |
| `GET /api/solar/solar_resource/v1.json` | Solar resource data for a location. Params: `lat`, `lon`. |
| `GET /api/alt-fuel-stations/v1.json` | Alternative-fuel (EV, etc.) stations. Params: `fuel_type`, `state`, `limit`. |
| `GET /api/pvwatts/v8.json` | PVWatts solar production estimates. |

```bash
curl "https://developer.nrel.gov/api/utility_rates/v3.json?api_key=$DATA_GOV_API_KEY&lat=40&lon=-105"
```

## Regulations.gov

Base: `https://api.regulations.gov/v4`

| Endpoint | Purpose |
| --- | --- |
| `GET /documents` | Search regulatory documents. Params: `filter[searchTerm]`, `filter[agencyId]`, `page[size]`, `page[number]`, `sort`. |
| `GET /documents/{documentId}` | One document. |
| `GET /comments` | Public comments. |
| `GET /dockets` | Rulemaking dockets. |

Follows JSON:API conventions (`data[]`, `attributes`, bracketed params).

```bash
curl -H "X-Api-Key: $DATA_GOV_API_KEY" \
  "https://api.regulations.gov/v4/documents?filter\[searchTerm\]=water&page\[size\]=5"
```

## FEC (Federal Election Commission)

Base: `https://api.open.fec.gov/v1`

| Endpoint | Purpose |
| --- | --- |
| `GET /candidates` | Search candidates. Params: `q`, `election_year`, `office` (`H`/`S`/`P`), `state`. |
| `GET /committees` | Political committees. |
| `GET /schedules/schedule_a` | Individual contributions. |

FEC uses `api_key` as a query param (it also accepts the header). Results under
`results[]`, paging under `pagination`.

```bash
curl "https://api.open.fec.gov/v1/candidates/?api_key=$DATA_GOV_API_KEY&q=smith&office=H"
```

## GovInfo

Base: `https://api.govinfo.gov`

| Endpoint | Purpose |
| --- | --- |
| `GET /collections` | List available collections (bills, CFR, Federal Register, etc.). |
| `GET /collections/{collection}/{startDate}/{endDate}` | Packages in a date range. |
| `GET /packages/{packageId}/summary` | Package metadata. |
| `GET /search` (POST on some versions) | Full-text search. |

```bash
curl -H "X-Api-Key: $DATA_GOV_API_KEY" \
  "https://api.govinfo.gov/collections?pageSize=10"
```

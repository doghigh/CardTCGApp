# AI Adoption Cost Dashboard

A finance toolkit for local organisations (small businesses, nonprofits, local
government, community institutions) evaluating the true cost of adopting an
AI solution. It separates **capital expenditure (CapEx)** from **operational
expenditure (OpEx)**, benchmarks a proposed initiative against illustrative
market ranges, and rolls everything into an interactive, multi-year
total-cost-of-ownership (TCO) dashboard.

Open `index.html` in any browser — no server, build step, or internet
connection required. All data stays in the browser (optionally cached to
`localStorage` so a session survives a reload); nothing is uploaded anywhere.

---

## 1. User requirements analysis

### 1.1 Primary users

| Persona | Need |
|---|---|
| **Owner / Executive Director** | A plain-English answer to "what will this actually cost us, this year and over time?" before approving a project. |
| **Finance / Bookkeeper** | CapEx vs OpEx split for budgeting, depreciation planning, and cash-flow forecasting. |
| **Ops / IT lead proposing the initiative** | A defensible cost estimate to bring to leadership, benchmarked so it doesn't look arbitrary. |
| **Board / Funder (nonprofit context)** | A comparison across multiple proposed initiatives to prioritise limited budget. |

### 1.2 Core user stories

1. As a finance lead, I want to enter the cost line items for a proposed AI
   initiative and immediately see the CapEx/OpEx split, so I know how much
   hits the balance sheet vs the annual budget.
2. As an ops lead, I want each line item benchmarked against a market range
   for organisations of my size, so I can tell if a vendor quote is high,
   low, or typical.
3. As an executive, I want a multi-year total-cost-of-ownership projection
   (not just year one), so recurring subscription/compute/support costs
   don't get underestimated.
4. As a board member, I want to compare several proposed initiatives
   side-by-side in one portfolio view, so we can prioritise.
5. As any user, I want to export the model as CSV, so it can be dropped into
   existing spreadsheets and board packs.

### 1.3 Functional requirements derived from the above

- Multi-initiative portfolio (add/remove/duplicate initiatives).
- Per-initiative inputs for 4 CapEx line items and 4 OpEx (annual) line
  items, each with an editable value and a visible benchmark range.
- Automatic classification of each entered value as **below / within /
  above** the benchmark range for that organisation size and category.
- Configurable projection horizon (1–5 years) and annual OpEx growth rate,
  to model inflation, usage growth, or vendor price increases.
- Portfolio-level totals: CapEx, Year-1 OpEx, N-year TCO.
- Visual breakdown: CapEx vs OpEx split, cost by category, cumulative
  multi-year cost trajectory.
- CSV export of the full model (inputs + computed totals).
- No backend, no tracking, no external data calls — the model is meant to be
  audited and edited by the user, not treated as a black box.

### 1.4 Explicit non-goals

- This is **not** a substitute for vendor quotes, tax/depreciation advice,
  or accounting sign-off. It is a structuring and sanity-checking tool for
  the conversation that happens *before* those quotes are gathered.
- The benchmark ranges are **illustrative starting assumptions**, not a
  licensed market-data feed (see §2.3). Treat them as a prior to be
  replaced with real numbers as they're collected.

---

## 2. The financial model

### 2.1 CapEx vs OpEx, as used here

- **CapEx (one-time)** — costs incurred to stand the initiative up:
  - `hardware` — new devices, edge/on-prem compute, cameras, networking
    upgrades, scanners, etc.
  - `softwareSetup` — platform onboarding fees, perpetual/initial licenses,
    one-time configuration.
  - `implementation` — integration, data migration, custom development,
    consulting/systems-integrator fees.
  - `training` — initial staff training and change-management cost to get
    the initiative live.
- **OpEx (annual, recurring)** — cost of keeping the initiative running:
  - `subscription` — SaaS/platform licensing, per-seat or per-workflow fees.
  - `compute` — cloud hosting, model inference/API usage.
  - `support` — maintenance contracts, vendor support tiers, patching.
  - `staffing` — internal FTE time allocated to operating/overseeing the
    initiative (prompt engineering, data stewardship, monitoring), costed at
    a blended internal rate.

### 2.2 How benchmark ranges are built (auditable, not a black box)

Each of 6 initiative categories has a **base range** (low–high, USD) per
line item, defined for a "small" organisation (10–49 employees). Those base
ranges are scaled by an **organisation-size multiplier**:

| Org size | Multiplier |
|---|---|
| Micro (1–9 employees) | 0.4× |
| Small (10–49 employees) | 1.0× |
| Medium (50–249 employees) | 3.2× |

Both the base ranges and the multipliers are declared as plain constants at
the top of `index.html` (`CATEGORY_BASE`, `ORG_MULTIPLIER`) — open the file
in a text editor and every number the dashboard uses is visible and
editable in one place. **These starting ranges are directional estimates
assembled from typical small-business SaaS/AI-vendor pricing patterns, not
a sourced market-research report.** Before using this to justify a real
budget, replace the base ranges with actual vendor quotes and your own
organisation's history — that's the intended workflow, not a limitation to
route around.

### 2.3 Initiative categories modelled

1. Customer Service Chatbot / Virtual Assistant
2. Predictive Analytics & Forecasting
3. Computer Vision / Process Automation
4. Generative Content & Copywriting
5. Workflow Automation (AI-augmented RPA)
6. Custom / Other AI Initiative (wide generic range, for anything that
   doesn't fit the above)

### 2.4 TCO calculation

For a projection horizon of `N` years and annual OpEx growth rate `g`:

```
CapEx total        = hardware + softwareSetup + implementation + training
Year-t OpEx         = (subscription + compute + support + staffing) × (1 + g)^(t-1)
N-year TCO          = CapEx total + Σ(t=1..N) Year-t OpEx
```

Portfolio totals are the sum of these across every initiative in the
dashboard.

---

## 3. Using the dashboard

1. Open `index.html` in a browser.
2. Click **Add initiative**, pick a category and organisation size — the
   fields pre-fill with the midpoint of the benchmark range.
3. Overwrite any field with your real vendor quote or internal estimate.
   The badge next to each field tells you whether it's below, within, or
   above the benchmark range for that category/size.
4. Adjust the projection horizon and annual growth rate to match your
   planning period.
5. Read the portfolio summary (CapEx vs OpEx split, cost-by-category chart,
   cumulative multi-year trajectory) at the top.
6. Click **Export CSV** to drop the model into a spreadsheet or board pack.

Data is cached to the browser's `localStorage` so a reload doesn't lose your
work; nothing leaves the browser.

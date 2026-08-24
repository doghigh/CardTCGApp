# data.gov MCP connector

A [Model Context Protocol](https://modelcontextprotocol.io) server that connects
Claude (Claude Code, Claude Desktop, or any MCP client) to U.S. government open
data through the **`api.data.gov` gateway** and the **`catalog.data.gov` CKAN
catalog**.

`api.data.gov` is a shared gateway that fronts many federal agency APIs (NASA,
USDA FoodData Central, Dept. of Education College Scorecard, NREL, Regulations.gov,
FEC, GovInfo, and more) with one API key, consistent rate limiting, and uniform
errors. This connector handles the key, HTTPS, rate-limit headers, and error
decoding for you.

> Companion skill: [`.claude/skills/data-gov`](../../.claude/skills/data-gov)
> teaches Claude the API's auth/rate-limit/error model and the participating
> agency endpoints. Skill = knowledge; connector = the callable tools.

## Tools

| Tool | What it does | Needs key? |
| --- | --- | --- |
| `datagov_request` | Authenticated GET to **any** gateway-managed URL/path — the escape hatch for APIs without a dedicated tool | yes |
| `catalog_search` | Discover datasets in the CKAN catalog (`package_search`) | no |
| `catalog_package_show` | Full metadata + resources for one dataset | no |
| `nasa_apod` | NASA Astronomy Picture of the Day | yes |
| `college_scorecard_search` | Search U.S. colleges (Dept. of Education) | yes |
| `fooddata_search` | Search USDA FoodData Central nutrition data | yes |
| `nrel_utility_rates` | Average electricity rates for a lat/lon (NREL) | yes |

## Setup

1. **Get a free API key** at https://api.data.gov/signup/ (instant, email-verified).
   Without one, the connector falls back to the shared `DEMO_KEY`, which is
   throttled to ~30 requests/hour and 50/day — fine for a smoke test, not for
   real use.

2. **Install dependencies** (a virtualenv is recommended):

   ```bash
   cd connectors/data-gov-mcp
   python -m pip install -r requirements.txt
   ```

3. **Set the key** in your environment:

   ```bash
   export DATA_GOV_API_KEY="your-key-here"
   ```

## Register the connector with your MCP client

### Claude Code (this repo)

A portable `.mcp.json` at the repo root already registers the `data-gov` server.
It reads the key from your environment (`DATA_GOV_API_KEY`), falling back to
`DEMO_KEY` if unset, so exporting a real key is all you need:

```bash
export DATA_GOV_API_KEY="your-key-here"
```

The tools then become available in the session.

### Any MCP client (generic stdio config)

```json
{
  "mcpServers": {
    "data-gov": {
      "command": "python",
      "args": ["connectors/data-gov-mcp/server.py"],
      "env": { "DATA_GOV_API_KEY": "your-key-here" }
    }
  }
}
```

Use an absolute path to `server.py` if your client's working directory differs
from the repo root.

## Try it

Run the server directly to confirm it starts (it speaks stdio and waits for a
client, so it will block — Ctrl-C to exit):

```bash
DATA_GOV_API_KEY=DEMO_KEY python server.py
```

Then, from your MCP client, ask things like:

- "Search the data.gov catalog for wildfire datasets."
- "What's today's NASA astronomy picture?"
- "Find California colleges with the lowest admission rates."
- "Look up the nutrition facts for cheddar cheese."

## Security notes

- The key is sent as an `X-Api-Key` header (never in a logged URL) and only to a
  fixed allowlist of known gateway hosts (`ALLOWED_GATEWAY_HOSTS` in
  `server.py`) — a mistyped or hostile host can never receive your credential.
- All requests are forced to HTTPS.
- Keep `DATA_GOV_API_KEY` out of committed files; use the environment variable.

"""data.gov MCP connector.

A Model Context Protocol server that connects Claude (or any MCP client) to the
U.S. government's open-data APIs through the ``api.data.gov`` gateway, plus the
``catalog.data.gov`` CKAN dataset catalog.

Design goals:
  * One shared credential. The data.gov key is read once from the
    ``DATA_GOV_API_KEY`` environment variable and injected on every gateway
    call, so tools never have to be handed a key.
  * Safe by default. Requests always go over HTTPS, the key travels in the
    ``X-Api-Key`` header (never in a logged URL), and the gateway's rate-limit
    headers and structured error codes are surfaced back to the caller instead
    of being swallowed.
  * A generic escape hatch (``datagov_request``) for any gateway-managed API,
    alongside a few curated convenience tools for the most-requested agencies.

Run it:  ``python server.py``  (stdio transport; configure it in your MCP
client — see README.md).
"""

from __future__ import annotations

import os
from typing import Any, Optional
from urllib.parse import urlparse

import requests
from mcp.server.fastmcp import FastMCP

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

# A real key is free from https://api.data.gov/signup/. DEMO_KEY works without
# signup but is throttled to ~30 requests/hour and 50/day per IP, so it exists
# only to make the connector usable out of the box for a quick smoke test.
API_KEY = os.environ.get("DATA_GOV_API_KEY", "DEMO_KEY")

# api.data.gov only fronts a known set of federal hosts. We refuse to attach the
# key to anything else so a mistyped or attacker-supplied host can never receive
# the credential. Add hosts here as you enroll in more gateway-managed APIs.
ALLOWED_GATEWAY_HOSTS = {
    "api.data.gov",
    "api.nasa.gov",
    "api.nal.usda.gov",          # USDA FoodData Central
    "developer.nrel.gov",        # NREL
    "api.regulations.gov",
    "api.open.fec.gov",
    "api.govinfo.gov",
    "api.trade.gov",
    "developer.trade.gov",
}

CATALOG_BASE = "https://catalog.data.gov/api/3/action"

DEFAULT_TIMEOUT = 30  # seconds

mcp = FastMCP("data-gov")


# --------------------------------------------------------------------------- #
# HTTP helpers
# --------------------------------------------------------------------------- #

def _normalize_gateway_url(url_or_path: str) -> str:
    """Turn a full URL or a leading-slash path into a validated https URL.

    A bare path (``/ed/collegescorecard/v1/schools``) is resolved against
    ``api.data.gov``. A full URL must point at one of ALLOWED_GATEWAY_HOSTS and
    is forced to https.
    """
    if url_or_path.startswith("/"):
        return "https://api.data.gov" + url_or_path

    parsed = urlparse(url_or_path)
    if not parsed.scheme:
        # e.g. "api.nasa.gov/planetary/apod" — treat as host + path
        parsed = urlparse("https://" + url_or_path)

    host = parsed.netloc.lower()
    if host not in ALLOWED_GATEWAY_HOSTS:
        raise ValueError(
            f"Host '{host}' is not a known api.data.gov-managed host. "
            f"Allowed hosts: {', '.join(sorted(ALLOWED_GATEWAY_HOSTS))}. "
            "Refusing to send the API key to an unknown host."
        )
    # Rebuild forcing https (HTTPS_REQUIRED otherwise) and preserving path/query.
    rebuilt = parsed._replace(scheme="https")
    return rebuilt.geturl()


def _describe_error(code: str) -> str:
    """Human-readable, actionable hint for a gateway error code."""
    hints = {
        "API_KEY_MISSING": "No API key was sent — set DATA_GOV_API_KEY.",
        "API_KEY_INVALID": "The API key was not recognized — check for typos.",
        "API_KEY_DISABLED": "This key was disabled — sign up for a new one at https://api.data.gov/signup/.",
        "API_KEY_UNAUTHORIZED": "This key isn't authorized for this API — some agencies require separate enrollment.",
        "API_KEY_UNVERIFIED": "The account's email isn't verified — click the link from the signup email.",
        "HTTPS_REQUIRED": "The request must use HTTPS.",
        "OVER_RATE_LIMIT": "Hourly rate limit exceeded (429) — back off until the window resets.",
        "NOT_FOUND": "The endpoint path or resource was not found — check the URL.",
    }
    return hints.get(code, "")


def _gateway_get(
    url_or_path: str, params: Optional[dict[str, Any]] = None
) -> dict[str, Any]:
    """GET a gateway-managed endpoint with the key injected via header.

    Returns a structured dict: on success ``{"ok": True, "status": ...,
    "rate_limit": {...}, "data": ...}``; on error a dict with ``ok: False`` and
    a decoded ``error_code`` / ``hint`` where the gateway supplied one. Network
    errors are returned as data rather than raised so the model gets a clear,
    non-fatal message.
    """
    try:
        url = _normalize_gateway_url(url_or_path)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}

    headers = {"X-Api-Key": API_KEY, "Accept": "application/json"}
    try:
        resp = requests.get(
            url, headers=headers, params=params or {}, timeout=DEFAULT_TIMEOUT
        )
    except requests.RequestException as exc:
        return {"ok": False, "error": f"Network error contacting {url}: {exc}"}

    rate_limit = {
        "limit": resp.headers.get("X-RateLimit-Limit"),
        "remaining": resp.headers.get("X-RateLimit-Remaining"),
    }

    # Parse body as JSON when possible; fall back to text.
    try:
        body: Any = resp.json()
    except ValueError:
        body = resp.text

    if resp.ok:
        return {
            "ok": True,
            "status": resp.status_code,
            "rate_limit": rate_limit,
            "data": body,
        }

    # Decode the gateway's structured error envelope when present.
    error_code = None
    error_message = None
    if isinstance(body, dict):
        err = body.get("error")
        if isinstance(err, dict):
            error_code = err.get("code")
            error_message = err.get("message")
        elif isinstance(body.get("errors"), list) and body["errors"]:
            first = body["errors"][0]
            if isinstance(first, dict):
                error_code = first.get("status") or first.get("code")
                error_message = first.get("detail") or first.get("title")

    result: dict[str, Any] = {
        "ok": False,
        "status": resp.status_code,
        "rate_limit": rate_limit,
        "error_code": error_code,
        "error": error_message or f"HTTP {resp.status_code}",
    }
    hint = _describe_error(error_code or "")
    if hint:
        result["hint"] = hint
    if error_code is None:
        # No structured envelope — hand back the raw body to aid debugging.
        result["body"] = body
    return result


def _catalog_get(action: str, params: dict[str, Any]) -> dict[str, Any]:
    """GET a CKAN Action API endpoint (no key required)."""
    url = f"{CATALOG_BASE}/{action}"
    try:
        resp = requests.get(url, params=params, timeout=DEFAULT_TIMEOUT)
    except requests.RequestException as exc:
        return {"ok": False, "error": f"Network error contacting {url}: {exc}"}
    try:
        body = resp.json()
    except ValueError:
        return {
            "ok": False,
            "status": resp.status_code,
            "error": "Catalog returned non-JSON response.",
            "body": resp.text[:2000],
        }
    if not resp.ok or not body.get("success", False):
        return {
            "ok": False,
            "status": resp.status_code,
            "error": body.get("error", f"HTTP {resp.status_code}"),
        }
    return {"ok": True, "status": resp.status_code, "result": body.get("result")}


# --------------------------------------------------------------------------- #
# Generic gateway tool
# --------------------------------------------------------------------------- #

@mcp.tool()
def datagov_request(url_or_path: str, params: Optional[dict[str, Any]] = None) -> dict:
    """Make an authenticated GET request to any api.data.gov-managed API.

    This is the escape hatch for agency APIs that don't have a dedicated tool.
    The data.gov key is injected automatically (X-Api-Key header, HTTPS forced),
    and rate-limit headers plus decoded error codes are returned.

    Args:
        url_or_path: Either a full URL to an allowed gateway host
            (e.g. "https://api.nasa.gov/planetary/apod") or a leading-slash path
            resolved against api.data.gov
            (e.g. "/ed/collegescorecard/v1/schools").
        params: Optional query parameters as a dict.

    Returns:
        {"ok": True, "status", "rate_limit", "data"} on success, or
        {"ok": False, "error", "error_code", "hint", ...} on failure.
    """
    return _gateway_get(url_or_path, params)


# --------------------------------------------------------------------------- #
# Catalog (CKAN) discovery tools — no key required
# --------------------------------------------------------------------------- #

@mcp.tool()
def catalog_search(
    query: str,
    rows: int = 10,
    start: int = 0,
    fq: Optional[str] = None,
    sort: Optional[str] = None,
) -> dict:
    """Search the catalog.data.gov dataset catalog (CKAN package_search).

    Use this to discover which datasets exist for a topic and who publishes
    them. No API key is required.

    Args:
        query: Free-text search terms (CKAN ``q``).
        rows: Number of datasets to return (max 1000).
        start: Result offset for pagination.
        fq: Optional Solr filter query, e.g. "organization:noaa-gov" or
            "res_format:CSV".
        sort: Optional sort, e.g. "metadata_modified desc".

    Returns:
        {"ok": True, "count", "datasets": [{title, name, notes, organization,
        tags, resources}]} — ``name`` is the slug to pass to
        ``catalog_package_show``.
    """
    params: dict[str, Any] = {"q": query, "rows": max(0, min(rows, 1000)), "start": start}
    if fq:
        params["fq"] = fq
    if sort:
        params["sort"] = sort

    res = _catalog_get("package_search", params)
    if not res.get("ok"):
        return res

    result = res["result"] or {}
    datasets = []
    for pkg in result.get("results", []):
        datasets.append(
            {
                "title": pkg.get("title"),
                "name": pkg.get("name"),
                "notes": (pkg.get("notes") or "")[:500],
                "organization": (pkg.get("organization") or {}).get("title"),
                "tags": [t.get("name") for t in pkg.get("tags", [])],
                "num_resources": pkg.get("num_resources"),
                "resources": [
                    {"name": r.get("name"), "format": r.get("format"), "url": r.get("url")}
                    for r in pkg.get("resources", [])
                ],
            }
        )
    return {"ok": True, "count": result.get("count"), "datasets": datasets}


@mcp.tool()
def catalog_package_show(dataset_id: str) -> dict:
    """Fetch full metadata for one dataset from catalog.data.gov (package_show).

    Args:
        dataset_id: The dataset slug (``name``) or UUID, e.g. from
            ``catalog_search`` results.

    Returns:
        {"ok": True, "dataset": {title, notes, organization, tags, resources}}
        where each resource has its url/format/description — the pointer to the
        actual data or live API endpoint.
    """
    res = _catalog_get("package_show", {"id": dataset_id})
    if not res.get("ok"):
        return res
    pkg = res["result"] or {}
    return {
        "ok": True,
        "dataset": {
            "title": pkg.get("title"),
            "name": pkg.get("name"),
            "notes": pkg.get("notes"),
            "organization": (pkg.get("organization") or {}).get("title"),
            "tags": [t.get("name") for t in pkg.get("tags", [])],
            "resources": [
                {
                    "name": r.get("name"),
                    "format": r.get("format"),
                    "url": r.get("url"),
                    "description": r.get("description"),
                }
                for r in pkg.get("resources", [])
            ],
        },
    }


# --------------------------------------------------------------------------- #
# Curated convenience tools
# --------------------------------------------------------------------------- #

@mcp.tool()
def nasa_apod(date: Optional[str] = None) -> dict:
    """NASA Astronomy Picture of the Day.

    Args:
        date: Optional date as YYYY-MM-DD. Defaults to today.

    Returns:
        The gateway response; ``data`` has title, explanation, url (image),
        media_type, and date.
    """
    params = {"date": date} if date else None
    return _gateway_get("https://api.nasa.gov/planetary/apod", params)


@mcp.tool()
def college_scorecard_search(
    fields: str,
    state: Optional[str] = None,
    name: Optional[str] = None,
    per_page: int = 10,
    page: int = 0,
    extra_params: Optional[dict[str, Any]] = None,
) -> dict:
    """Search U.S. colleges via the Dept. of Education College Scorecard API.

    Args:
        fields: Comma-separated fields to return (required — responses are
            enormous otherwise). Example:
            "id,school.name,school.state,latest.student.size,"
            "latest.admissions.admission_rate.overall".
        state: Optional two-letter state filter (school.state).
        name: Optional institution name filter (school.name).
        per_page: Results per page (max 100).
        page: Page number (0-based).
        extra_params: Any additional Scorecard params, e.g.
            {"latest.admissions.admission_rate.overall__range": "0..0.2"}.

    Returns:
        Gateway response; ``data.results`` holds the schools,
        ``data.metadata`` holds paging info.
    """
    params: dict[str, Any] = {"fields": fields, "per_page": min(per_page, 100), "page": page}
    if state:
        params["school.state"] = state
    if name:
        params["school.name"] = name
    if extra_params:
        params.update(extra_params)
    return _gateway_get("/ed/collegescorecard/v1/schools", params)


@mcp.tool()
def fooddata_search(query: str, data_type: Optional[str] = None, page_size: int = 10) -> dict:
    """Search USDA FoodData Central for foods and their nutrient data.

    Args:
        query: Food search terms, e.g. "cheddar cheese".
        data_type: Optional comma-separated types to restrict to, e.g.
            "Foundation,SR Legacy,Branded".
        page_size: Number of results (max 200).

    Returns:
        Gateway response; ``data.foods`` holds matches. Each food's
        ``foodNutrients`` lists nutrientName/unitName/value.
    """
    params: dict[str, Any] = {"query": query, "pageSize": min(page_size, 200)}
    if data_type:
        params["dataType"] = data_type
    return _gateway_get("https://api.nal.usda.gov/fdc/v1/foods/search", params)


@mcp.tool()
def nrel_utility_rates(lat: float, lon: float) -> dict:
    """Average electricity utility rates for a location (NREL).

    Args:
        lat: Latitude.
        lon: Longitude.

    Returns:
        Gateway response; ``data.outputs`` has residential/commercial/
        industrial ($/kWh) rates and the serving utility name.
    """
    return _gateway_get(
        "https://developer.nrel.gov/api/utility_rates/v3.json",
        {"lat": lat, "lon": lon},
    )


if __name__ == "__main__":
    mcp.run()

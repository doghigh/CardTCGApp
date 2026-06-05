"""
Card valuation — Scryfall (MTG), eBay Browse API, and PriceCharting fallback.

Source priority:
  - Magic: The Gathering → Scryfall (free official API, real USD prices)
  - Everything else      → eBay Browse API (real sold/active data)
  - Fallback             → PriceCharting scrape (throttled, 429-aware)

eBay API Compliance — Marketplace Account Deletion:
  This app uses only public eBay data via App-level OAuth (no user tokens).
  It does NOT store any eBay user account data and qualifies for opt-out.
  Endpoint registered at: https://cardtcgapp.onrender.com/ebay/deletion
  Reference: https://developer.ebay.com/develop/guides-v2/marketplace-user-account-deletion

Environment variables:
  EBAY_APP_ID   — Client ID from developer.ebay.com (required)
  EBAY_CERT_ID  — Client Secret from developer.ebay.com (required for Browse API)
"""

import base64
import os
import re
import time
import logging
import threading
import requests
from datetime import datetime, timedelta
from statistics import median
from typing import List, Dict, Optional, Tuple
from urllib.parse import quote

logger = logging.getLogger(__name__)

# Scryfall — free official Magic: The Gathering card API (prices in USD)
SCRYFALL_NAMED_URL  = "https://api.scryfall.com/cards/named"
SCRYFALL_SEARCH_URL = "https://api.scryfall.com/cards/search"

# eBay OAuth token endpoint
OAUTH_URL_PROD    = "https://api.ebay.com/identity/v1/oauth2/token"
OAUTH_URL_SANDBOX = "https://api.sandbox.ebay.com/identity/v1/oauth2/token"

# eBay Browse API
BROWSE_URL_PROD    = "https://api.ebay.com/buy/browse/v1/item_summary/search"
BROWSE_URL_SANDBOX = "https://api.sandbox.ebay.com/buy/browse/v1/item_summary/search"

# Scope needed for public/app-level Browse API access
BROWSE_SCOPE = "https://api.ebay.com/oauth/api_scope"

# Condition multipliers keyed on grade. Must cover every grade the inspector
# emits (Gem Mint, Mint, Near Mint, Excellent, Very Good, Good, Played, Poor)
# plus the legacy Pristine/Fair labels.
CONDITION_MULTIPLIERS = {
    "Gem Mint":  1.50,
    "Pristine":  1.40,
    "Mint":      1.25,
    "Near Mint": 1.10,
    "Excellent": 0.90,
    "Very Good": 0.75,
    "Good":      0.55,
    "Fair":      0.40,
    "Played":    0.40,
    "Poor":      0.25,
}


class CardValuator:
    """
    Two-source valuation:
      1. eBay Browse API  — active listing prices (requires App ID + Cert ID)
      2. eBay web scrape  — completed/sold prices  (no API key needed)

    Both are attempted; sold prices are weighted more heavily in the estimate.
    """

    def __init__(self):
        # OAuth token cache
        self._token: Optional[str] = None
        self._token_expiry: datetime = datetime.utcnow()
        self.reload_credentials()

        # API session — clean headers for eBay OAuth / Browse API
        self.api_session = requests.Session()
        self.api_session.headers.update({
            "User-Agent": "TradingCardManager/1.1",
            "Accept":     "application/json",
        })

        # Scrape session — full browser fingerprint to avoid 403
        self.scrape_session = requests.Session()
        self.scrape_session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;"
                "q=0.9,image/avif,image/webp,*/*;q=0.8"
            ),
            "Accept-Language":    "en-US,en;q=0.9",
            "Accept-Encoding":    "gzip, deflate, br",
            "Connection":         "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest":     "document",
            "Sec-Fetch-Mode":     "navigate",
            "Sec-Fetch-Site":     "none",
            "Sec-Fetch-User":     "?1",
            "DNT":                "1",
        })

        self.api_timeout   = 20   # OAuth + Browse API calls
        self.scrape_timeout = 15  # web scrape

        # Thread-safe scrape throttle — PriceCharting returns 429 if hammered.
        # Shared across the batch-import worker threads (one valuator instance).
        self._scrape_lock = threading.Lock()
        self._last_scrape = 0.0
        self.scrape_min_interval = 2.0   # seconds between scrape requests

        # Scryfall throttle (its docs ask for ~100ms between requests)
        self._scryfall_lock = threading.Lock()
        self._last_scryfall = 0.0
        self.scryfall_min_interval = 0.12

    def reload_credentials(self):
        """(Re)read eBay keys from the environment and reset the token cache."""
        self._app_id  = os.environ.get("EBAY_APP_ID",  "").strip()
        self._cert_id = os.environ.get("EBAY_CERT_ID", "").strip()
        self._sandbox = "SBX" in self._app_id.upper()
        self._oauth_url  = OAUTH_URL_SANDBOX  if self._sandbox else OAUTH_URL_PROD
        self._browse_url = BROWSE_URL_SANDBOX if self._sandbox else BROWSE_URL_PROD
        self._token = None
        self._token_expiry = datetime.utcnow()

        if self._sandbox:
            logger.info("eBay Valuator: SANDBOX mode — prices are test data only.")
        if not self._cert_id:
            logger.info("EBAY_CERT_ID not set — Browse API disabled, using web scrape only.")

    # ------------------------------------------------------------------ #
    #  OAuth token (Client Credentials — app-level, no user login needed)  #
    # ------------------------------------------------------------------ #

    def _get_token(self) -> Optional[str]:
        """Return a cached or freshly fetched OAuth access token."""
        if not self._app_id or not self._cert_id:
            return None
        if self._token and datetime.utcnow() < self._token_expiry:
            return self._token

        try:
            credentials = base64.b64encode(
                f"{self._app_id}:{self._cert_id}".encode()
            ).decode()
            r = self.api_session.post(
                self._oauth_url,
                headers={
                    "Authorization": f"Basic {credentials}",
                    "Content-Type":  "application/x-www-form-urlencoded",
                },
                data={
                    "grant_type": "client_credentials",
                    "scope":      BROWSE_SCOPE,
                },
                timeout=self.api_timeout,
            )
            r.raise_for_status()
            data = r.json()
            self._token = data["access_token"]
            # Expire 5 minutes early to avoid edge cases
            self._token_expiry = (datetime.utcnow()
                                  + timedelta(seconds=data.get("expires_in", 7200) - 300))
            logger.debug("eBay OAuth token obtained (expires %s)", self._token_expiry)
            return self._token
        except Exception as exc:
            logger.warning("eBay OAuth token request failed: %s", exc)
            return None

    # ------------------------------------------------------------------ #
    #  Source 1: eBay Browse API — active listings                         #
    # ------------------------------------------------------------------ #

    def search_browse_api(self, card_name: str, set_name: Optional[str] = None,
                          game: Optional[str] = None) -> Optional[Dict]:
        """Search eBay Browse API for current active listing prices."""
        token = self._get_token()
        if not token:
            return None

        query = self._build_query(card_name, set_name, game)

        params = {
            "q":               query,
            "limit":           "100",
            "sort":            "price",
            "filter":          "buyingOptions:{FIXED_PRICE|AUCTION|AUCTION_WITH_BIN}",
        }
        # Only constrain the category when we're confident about the type.
        # Non-sport cards (Star Wars, Garbage Pail Kids, etc. → "Other") must
        # NOT be forced into the CCG category or eBay returns nothing.
        category = self._ebay_category(game)
        if category:
            params["category_ids"] = category

        try:
            browse_headers = {
                "Authorization":           f"Bearer {token}",
                "X-EBAY-C-MARKETPLACE-ID": "EBAY_US",
                "X-EBAY-C-ENDUSERCTX":     "contextualLocation=country=US",
            }
            r = self.api_session.get(
                self._browse_url, params=params,
                headers=browse_headers,
                timeout=self.api_timeout,
            )
            if r.status_code == 401:
                self._token = None
                token = self._get_token()
                if not token:
                    return None
                browse_headers["Authorization"] = f"Bearer {token}"
                r = self.api_session.get(
                    self._browse_url, params=params,
                    headers=browse_headers,
                    timeout=self.api_timeout,
                )
            r.raise_for_status()
            return self._parse_browse_response(r.json(), query)
        except Exception as exc:
            logger.warning("eBay Browse API error: %s", exc)
            return None

    def _parse_browse_response(self, data: dict, query: str) -> Optional[Dict]:
        """Extract prices from Browse API JSON response."""
        items = data.get("itemSummaries", [])
        if not items:
            return None

        prices: List[float] = []
        for item in items:
            price_info = item.get("price", {})
            try:
                price = float(price_info.get("value", 0))
                if 0.25 < price < 50_000:
                    prices.append(price)
            except (ValueError, TypeError):
                pass

        if not prices:
            return None

        prices.sort()
        trim = max(1, len(prices) // 10)
        trimmed = prices[trim: len(prices) - trim] or prices

        logger.info("eBay Browse API: %d active listings for '%s', median=$%.2f",
                    len(trimmed), query, median(trimmed))
        return {
            "source":  "eBay Browse (active)",
            "value":   round(median(trimmed), 2),
            "low":     round(min(trimmed), 2),
            "high":    round(max(trimmed), 2),
            "sample":  len(trimmed),
            "query":   query,
        }

    # ------------------------------------------------------------------ #
    #  Source: Scryfall — free official MTG pricing (no key, reliable)     #
    # ------------------------------------------------------------------ #

    def _is_mtg(self, game: Optional[str]) -> bool:
        if not game:
            return False
        g = game.lower()
        return "magic" in g or "mtg" in g

    def _scryfall_set_code(self, set_name: Optional[str]) -> Optional[str]:
        """Return a Scryfall set code if set_name looks like one (e.g. AKH, W17)."""
        if not set_name:
            return None
        s = set_name.strip()
        return s.lower() if re.fullmatch(r"[A-Za-z0-9]{2,5}", s) else None

    def _scryfall_throttle(self):
        with self._scryfall_lock:
            elapsed = time.time() - self._last_scryfall
            if elapsed < self.scryfall_min_interval:
                time.sleep(self.scryfall_min_interval - elapsed)
            self._last_scryfall = time.time()

    @staticmethod
    def _scryfall_price(data: dict) -> Optional[float]:
        prices = data.get("prices") or {}
        for key in ("usd", "usd_foil", "usd_etched"):
            val = prices.get(key)
            if val:
                try:
                    return float(val)
                except (ValueError, TypeError):
                    pass
        return None

    def search_scryfall(self, card_name: str, set_name: Optional[str] = None,
                        game: Optional[str] = None) -> Optional[Dict]:
        """Look up a Magic card's market price from Scryfall (USD)."""
        if not self._is_mtg(game):
            return None
        name = (card_name or "").strip()
        if not name:
            return None

        # 1) Exact-ish lookup by name (+ set code if it looks valid)
        code = self._scryfall_set_code(set_name)
        attempts = ([{"fuzzy": name, "set": code}] if code else []) + [{"fuzzy": name}]
        for params in attempts:
            try:
                self._scryfall_throttle()
                r = self.api_session.get(SCRYFALL_NAMED_URL, params=params,
                                         timeout=self.api_timeout)
                if r.status_code in (400, 404):
                    continue
                r.raise_for_status()
                hit = self._scryfall_result(r.json(), name)
                if hit:
                    return hit
            except Exception as exc:
                logger.warning("Scryfall named lookup failed for '%s': %s", name, exc)
                break

        # 2) Fallback: search ALL printings of this exact name, cheapest priced
        #    first. Rescues cards whose specific printing had no USD price (e.g.
        #    a token reprint) or where the set field was garbage.
        try:
            self._scryfall_throttle()
            r = self.api_session.get(
                SCRYFALL_SEARCH_URL,
                params={"q": f'!"{name}" game:paper', "order": "usd", "dir": "asc",
                        "unique": "prints"},
                timeout=self.api_timeout,
            )
            if r.status_code == 200:
                for card in r.json().get("data", []):
                    hit = self._scryfall_result(card, name)
                    if hit:
                        return hit
        except Exception as exc:
            logger.warning("Scryfall search fallback failed for '%s': %s", name, exc)

        return None

    def _scryfall_result(self, data: dict, name: str) -> Optional[Dict]:
        """Build a valuation dict from a Scryfall card object, or None."""
        price = self._scryfall_price(data)
        if price is None or price <= 0:
            return None
        set_disp = (data.get("set") or "").upper()
        logger.info("Scryfall: %s (%s) = $%.2f", name, set_disp, price)
        return {
            "source": f"Scryfall ({set_disp})" if set_disp else "Scryfall",
            "value":  round(price, 2),
            "low":    round(price, 2),
            "high":   round(price, 2),
            "sample": 1,
            "query":  name,
        }

    # ------------------------------------------------------------------ #
    #  Source 2: PriceCharting — historical sold prices                    #
    # ------------------------------------------------------------------ #

    def _scrape_get(self, url: str, max_retries: int = 3):
        """
        Thread-safe, rate-limited GET for scrape targets.

        Enforces a minimum interval between requests (shared across threads)
        and backs off on HTTP 429, honouring Retry-After. Returns the Response
        or None if it kept being rate-limited.
        """
        for attempt in range(max_retries + 1):
            with self._scrape_lock:
                elapsed = time.time() - self._last_scrape
                if elapsed < self.scrape_min_interval:
                    time.sleep(self.scrape_min_interval - elapsed)
                try:
                    r = self.scrape_session.get(url, timeout=self.scrape_timeout)
                finally:
                    self._last_scrape = time.time()

                if r.status_code != 429:
                    r.raise_for_status()
                    return r

                # Rate limited — pause everyone (still holding the lock) then retry
                retry_after = r.headers.get("Retry-After", "")
                if retry_after.isdigit():
                    delay = min(float(retry_after), 30.0)
                else:
                    delay = min(self.scrape_min_interval * (2 ** (attempt + 1)), 30.0)
                logger.warning("Scrape 429 — backing off %.1fs (attempt %d/%d)",
                               delay, attempt + 1, max_retries)
                time.sleep(delay)
                self._last_scrape = time.time()

        logger.warning("Scrape gave up after %d retries (still 429): %s",
                       max_retries, url)
        return None

    def search_pricecharting(self, card_name: str, set_name: Optional[str] = None,
                             game: Optional[str] = None) -> Optional[Dict]:
        """Scrape PriceCharting for sold/historical card prices."""
        try:
            query = card_name
            if set_name:
                query += f" {set_name}"

            url = (
                f"https://www.pricecharting.com/search-products"
                f"?q={quote(query)}&type=prices"
            )
            r = self._scrape_get(url)
            if r is None:
                return None

            # Extract prices from the results table
            prices: List[float] = []
            for m in re.finditer(
                r'<td[^>]*class="[^"]*price[^"]*"[^>]*>\s*\$?([\d,]+\.?\d{0,2})',
                r.text, re.I
            ):
                try:
                    v = float(m.group(1).replace(",", ""))
                    if 0.25 < v < 50_000:
                        prices.append(v)
                except ValueError:
                    pass

            # Wider fallback
            if not prices:
                for m in re.finditer(r'\$([\d,]+\.\d{2})', r.text):
                    try:
                        v = float(m.group(1).replace(",", ""))
                        if 0.25 < v < 50_000:
                            prices.append(v)
                    except ValueError:
                        pass

            if not prices:
                logger.debug("PriceCharting: no prices for '%s'", query)
                return None

            prices.sort()
            trim = max(1, len(prices) // 10)
            trimmed = prices[trim: len(prices) - trim] or prices

            logger.info("PriceCharting: %d prices for '%s', median=$%.2f",
                        len(trimmed), query, median(trimmed))
            return {
                "source":  "PriceCharting",
                "value":   round(median(trimmed), 2),
                "low":     round(min(trimmed), 2),
                "high":    round(max(trimmed), 2),
                "sample":  len(trimmed),
                "query":   query,
            }
        except Exception as exc:
            logger.warning("PriceCharting scrape failed: %s", exc)
            return None

    # ------------------------------------------------------------------ #
    #  Helpers                                                             #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _ebay_category(game: Optional[str]) -> Optional[str]:
        """
        Map a game to an eBay category id, or None to search all categories.

        Returning None for non-sport / unknown types is deliberate: forcing a
        category would exclude legitimate results (e.g. 1980 Star Wars cards
        are Non-Sport singles, not CCG cards).
        """
        if not game:
            return None
        g = game.lower()
        sports = {"baseball", "basketball", "football", "hockey", "sports cards"}
        tcg = {"magic", "mtg", "pokémon", "pokemon", "yu-gi-oh", "yugioh",
               "one piece", "lorcana", "flesh and blood"}
        if g in sports:
            return "213"        # Sports Trading Card Singles
        if any(t in g for t in tcg):
            return "183454"     # CCG Individual Cards
        return None             # Non-sport / unknown → search everything

    def _build_query(self, card_name: str, set_name: Optional[str],
                     game: Optional[str]) -> str:
        parts = [card_name]
        if set_name and set_name.lower() not in card_name.lower():
            parts.append(set_name)
        if game:
            for kw in ["Pokémon", "Pokemon", "Magic", "Yu-Gi-Oh",
                       "Baseball", "Basketball", "Football", "Hockey"]:
                if kw.lower() in game.lower():
                    parts.append(kw)
                    break
        parts.append("card")
        return " ".join(parts)

    # ------------------------------------------------------------------ #
    #  Public interface                                                    #
    # ------------------------------------------------------------------ #

    def fetch_value(self, card_name: str, set_name: Optional[str] = None,
                    game: Optional[str] = None) -> Optional[Dict]:
        """
        Fetch best valuation from available sources.

        Priority:
          1. PriceCharting  — historical sold prices (most accurate)
          2. eBay Browse API — active listing prices (official API)
          3. Blend if both available: 70% PriceCharting + 30% Browse
          4. Browse-only: apply 15% discount (cards sell below asking)
        """
        if not card_name or not card_name.strip():
            return None

        # Magic cards: use Scryfall (free official API, real USD prices, no
        # rate-limit headaches). Avoids scraping PriceCharting entirely for MTG.
        if self._is_mtg(game):
            scry = self.search_scryfall(card_name, set_name, game)
            if scry:
                return scry

        # Try eBay Browse first — it's a real API with high rate limits. If it
        # returns a confident result, skip the PriceCharting scrape entirely.
        # This keeps large batch/re-value runs from tripping PriceCharting 429s.
        active = self.search_browse_api(card_name, set_name, game)
        if active and active.get("sample", 0) >= 5:
            return {**active,
                    "value":  round(active["value"] * 0.85, 2),
                    "source": "eBay Browse (active, est.)"}

        sold = self.search_pricecharting(card_name, set_name, game)

        if sold and active:
            blended = round(sold["value"] * 0.70 + active["value"] * 0.30, 2)
            return {
                "source":  f"Blended (PriceCharting + eBay, n={sold['sample'] + active['sample']})",
                "value":   blended,
                "low":     min(sold["low"],  active["low"]),
                "high":    max(sold["high"], active["high"]),
                "sample":  sold["sample"] + active["sample"],
                "query":   sold.get("query", ""),
            }

        if sold:
            return sold

        if active:
            return {**active,
                    "value":  round(active["value"] * 0.85, 2),
                    "source": "eBay Browse (active, est.)"}

        return None

    # Keep old method name for existing callers
    def fetch_all_values(self, card_name: str,
                         set_name: Optional[str] = None) -> List[Dict]:
        result = self.fetch_value(card_name, set_name)
        return [result] if result else []

    def compute_estimate(self, values: List[Dict],
                         condition_score: float = 85.0,
                         grade: Optional[str] = None) -> float:
        if not values:
            return 0.0
        base = median(sorted(v["value"] for v in values))
        if base <= 0:
            return 0.0
        if grade and grade in CONDITION_MULTIPLIERS:
            multiplier = CONDITION_MULTIPLIERS[grade]
        else:
            multiplier = max(0.25, min(1.50, condition_score / 85.0))
        est = round(base * multiplier, 2)
        # A card with a real market price should never display as $0.00 —
        # floor cheap commons at a penny so "found" is distinguishable from
        # "no data" (which legitimately stays $0.00).
        return max(est, 0.01)

    def value_summary(self, card_name: str, set_name: Optional[str] = None,
                      game: Optional[str] = None,
                      grade: Optional[str] = None,
                      condition_score: float = 85.0) -> Dict:
        result = self.fetch_value(card_name, set_name, game)
        if not result:
            return {"estimated": 0.0, "source": "No data",
                    "low": 0.0, "high": 0.0, "sample": 0}
        estimated = self.compute_estimate([result], condition_score, grade)
        return {
            "estimated": estimated,
            "source":    result.get("source", ""),
            "low":       result.get("low",    0.0),
            "high":      result.get("high",   0.0),
            "sample":    result.get("sample", 0),
            "query":     result.get("query",  ""),
        }

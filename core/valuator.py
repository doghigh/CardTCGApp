"""
Card valuation via eBay Finding API (sold listings) with web scrape fallbacks.

eBay API Compliance — Marketplace Account Deletion:
  This application uses ONLY the eBay Finding API with an App ID (client
  credentials). It queries PUBLIC sold listing prices and does NOT:
    - use eBay OAuth / user tokens
    - store any eBay user account data (usernames, IDs, feedback, etc.)
    - access any private or user-specific eBay resources

  As a result this app qualifies for the OPT-OUT path under eBay's
  Marketplace Account Deletion/Closure notification requirement.

  Action required on the eBay developer portal:
    1. Sign in at developer.ebay.com
    2. My Account → Application Keys → Production App
    3. Marketplace Account Deletion section → select "I don't store eBay user data"

  Reference: https://developer.ebay.com/develop/guides-v2/marketplace-user-account-deletion
"""

import os
import re
import logging
import requests
from datetime import datetime, timedelta
from statistics import median
from typing import List, Dict, Optional
from urllib.parse import quote
from xml.etree import ElementTree as ET

logger = logging.getLogger(__name__)

# eBay Finding API endpoints
FINDING_API_PROD    = "https://svcs.ebay.com/services/search/FindingService/v1"
FINDING_API_SANDBOX = "https://svcs.sandbox.ebay.com/services/search/FindingService/v1"

# Condition multipliers keyed on grade letter
CONDITION_MULTIPLIERS = {
    "Gem Mint":     1.50,
    "Pristine":     1.40,
    "Mint":         1.25,
    "Near Mint":    1.10,
    "Excellent":    0.90,
    "Very Good":    0.75,
    "Good":         0.55,
    "Fair":         0.40,
    "Poor":         0.25,
}


class CardValuator:
    """Fetches real sold-listing prices from eBay API with web-scrape fallbacks."""

    def __init__(self):
        self._app_id = os.environ.get("EBAY_APP_ID", "").strip()
        # Sandbox App IDs contain "-SBX-"; route to the right endpoint
        self._sandbox = "SBX" in self._app_id.upper()
        self._api_url = FINDING_API_SANDBOX if self._sandbox else FINDING_API_PROD
        if self._sandbox:
            logger.info("eBay Valuator: using SANDBOX endpoint — "
                        "results are test data only. "
                        "Get a Production App ID at developer.ebay.com to see real prices.")
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "TradingCardManager/1.1 (+https://github.com/doghigh/CardTCGApp)"
        })
        self.timeout = 12

    # ------------------------------------------------------------------ #
    #  Primary: eBay Finding API                                           #
    # ------------------------------------------------------------------ #

    def search_ebay_api(self, card_name: str, set_name: Optional[str] = None,
                        game: Optional[str] = None) -> Optional[Dict]:
        """Query eBay Finding API for completed (sold) listings."""
        if not self._app_id:
            logger.debug("EBAY_APP_ID not set — skipping API search")
            return None

        keywords = self._build_query(card_name, set_name, game)

        params = {
            "OPERATION-NAME":        "findCompletedItems",
            "SERVICE-VERSION":       "1.13.0",
            "SECURITY-APPNAME":      self._app_id,
            "RESPONSE-DATA-FORMAT":  "XML",
            "REST-PAYLOAD":          "",
            "keywords":              keywords,
            "categoryId":            "183454",  # Non-Sport Trading Card Games
            "itemFilter(0).name":    "SoldItemsOnly",
            "itemFilter(0).value":   "true",
            "itemFilter(1).name":    "ListingType",
            "itemFilter(1).value":   "AuctionWithBIN",
            "itemFilter(2).name":    "ListingType",
            "itemFilter(2).value":   "FixedPrice",
            "itemFilter(2).value":   "Auction",
            "sortOrder":             "EndTimeSoonest",
            "paginationInput.entriesPerPage": "100",
        }

        # Also try Sports Trading Cards category if game looks like a sport
        sports = {"baseball", "basketball", "football", "hockey", "sports cards"}
        if game and game.lower() in sports:
            params["categoryId"] = "213"  # Sports Trading Cards

        try:
            r = self.session.get(self._api_url, params=params, timeout=self.timeout)
            r.raise_for_status()
            return self._parse_finding_response(r.text, keywords)
        except requests.RequestException as exc:
            logger.warning("eBay API request failed: %s", exc)
            return None
        except Exception as exc:
            logger.warning("eBay API parse error: %s", exc)
            return None

    def _build_query(self, card_name: str, set_name: Optional[str],
                     game: Optional[str]) -> str:
        """Build a focused keyword string for eBay search."""
        parts = [card_name]
        if set_name and set_name.lower() not in card_name.lower():
            parts.append(set_name)
        # Add game hint for disambiguation
        if game:
            for keyword in ["Pokémon", "Pokemon", "Magic", "Yu-Gi-Oh", "Baseball",
                            "Basketball", "Football", "Hockey"]:
                if keyword.lower() in game.lower():
                    parts.append(keyword)
                    break
        parts.append("card")
        return " ".join(parts)

    def _parse_finding_response(self, xml_text: str, query: str) -> Optional[Dict]:
        """Extract sold prices from eBay Finding API XML response."""
        ns = {"ns": "http://www.notifications.ebay.com/v1"}
        # eBay uses a dynamic namespace — strip it for simple parsing
        xml_text = re.sub(r' xmlns[^"]*"[^"]*"', '', xml_text)
        root = ET.fromstring(xml_text)

        ack = root.findtext(".//ack") or ""
        if "Success" not in ack and "Warning" not in ack:
            logger.debug("eBay API ack: %s", ack)
            return None

        # Collect sellingStatus/currentPrice for sold items
        prices: List[float] = []
        cutoff = datetime.utcnow() - timedelta(days=90)

        for item in root.findall(".//item"):
            # Only include items that actually sold
            selling_state = item.findtext(".//sellingStatus/sellingState") or ""
            if "EndedWithSales" not in selling_state and "Sold" not in selling_state:
                # findCompletedItems with SoldItemsOnly=true should only return sold,
                # but double-check
                pass

            # End time filter — last 90 days
            end_time_str = item.findtext(".//listingInfo/endTime") or ""
            try:
                end_time = datetime.strptime(end_time_str[:19], "%Y-%m-%dT%H:%M:%S")
                if end_time < cutoff:
                    continue
            except ValueError:
                pass

            price_str = (item.findtext(".//sellingStatus/convertedCurrentPrice") or
                         item.findtext(".//sellingStatus/currentPrice") or "")
            try:
                price = float(price_str)
                if 0.50 < price < 50_000:   # sanity range
                    prices.append(price)
            except (ValueError, TypeError):
                pass

        if not prices:
            return None

        # Trim top/bottom 10% to remove outliers
        prices.sort()
        trim = max(1, len(prices) // 10)
        trimmed = prices[trim: len(prices) - trim] or prices

        return {
            "source":     "eBay (sold listings)",
            "value":      round(median(trimmed), 2),
            "low":        round(min(trimmed), 2),
            "high":       round(max(trimmed), 2),
            "sample":     len(trimmed),
            "query":      query,
        }

    # ------------------------------------------------------------------ #
    #  Fallback: eBay web scrape (no API key needed)                       #
    # ------------------------------------------------------------------ #

    def search_ebay_web(self, card_name: str,
                        set_name: Optional[str] = None) -> Optional[Dict]:
        """Scrape eBay sold listings as a fallback when API key unavailable."""
        try:
            query = self._build_query(card_name, set_name, None)
            url = (f"https://www.ebay.com/sch/i.html"
                   f"?_nkw={quote(query)}&LH_Sold=1&LH_Complete=1&_ipg=100")
            r = self.session.get(url, timeout=self.timeout)
            r.raise_for_status()

            prices = [
                float(m.group(1).replace(",", ""))
                for m in re.finditer(r'\$([\d,]+\.\d{2})', r.text)
                if 0.50 < float(m.group(1).replace(",", "")) < 50_000
            ]
            if not prices:
                return None

            prices.sort()
            trim = max(1, len(prices) // 4)
            trimmed = prices[trim: len(prices) - trim] or prices
            return {
                "source":  "eBay (scrape)",
                "value":   round(median(trimmed), 2),
                "low":     round(min(trimmed), 2),
                "high":    round(max(trimmed), 2),
                "sample":  len(trimmed),
            }
        except Exception as exc:
            logger.debug("eBay scrape failed: %s", exc)
            return None

    # ------------------------------------------------------------------ #
    #  Public interface                                                    #
    # ------------------------------------------------------------------ #

    def fetch_value(self, card_name: str, set_name: Optional[str] = None,
                    game: Optional[str] = None) -> Optional[Dict]:
        """Return best available valuation, preferring the official API."""
        if not card_name or not card_name.strip():
            return None

        result = self.search_ebay_api(card_name, set_name, game)
        if result and result.get("value", 0) > 0:
            return result

        # API unavailable or no results — fall back to scrape
        result = self.search_ebay_web(card_name, set_name)
        return result if result and result.get("value", 0) > 0 else None

    # Keep old method name so existing callers don't break
    def fetch_all_values(self, card_name: str,
                         set_name: Optional[str] = None) -> List[Dict]:
        result = self.fetch_value(card_name, set_name)
        return [result] if result else []

    def compute_estimate(self, values: List[Dict],
                         condition_score: float = 85.0,
                         grade: Optional[str] = None) -> float:
        """Condition-adjusted value using grade letter if available."""
        if not values:
            return 0.0

        base = median(sorted(v["value"] for v in values))

        if grade and grade in CONDITION_MULTIPLIERS:
            multiplier = CONDITION_MULTIPLIERS[grade]
        else:
            # Fall back to score-based multiplier (0.25 – 1.50)
            multiplier = max(0.25, min(1.50, condition_score / 85.0))

        return round(base * multiplier, 2)

    def value_summary(self, card_name: str, set_name: Optional[str] = None,
                      game: Optional[str] = None,
                      grade: Optional[str] = None,
                      condition_score: float = 85.0) -> Dict:
        """Single call that returns a full valuation summary dict."""
        result = self.fetch_value(card_name, set_name, game)
        if not result:
            return {"estimated": 0.0, "source": "No data", "low": 0.0,
                    "high": 0.0, "sample": 0}

        estimated = self.compute_estimate([result], condition_score, grade)
        return {
            "estimated": estimated,
            "source":    result.get("source", ""),
            "low":       result.get("low", 0.0),
            "high":      result.get("high", 0.0),
            "sample":    result.get("sample", 0),
            "query":     result.get("query", ""),
        }

import requests
from bs4 import BeautifulSoup
import re
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Optional


class CardValuator:
    """Fetches and computes card market values from multiple sources."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                          'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36'
        })
        self.timeout = 12

    def search_tcgplayer(self, card_name: str, set_name: str = None) -> Optional[Dict]:
        """Search TCGPlayer for current price."""
        try:
            query = card_name + (f" {set_name}" if set_name else "")
            url = f"https://www.tcgplayer.com/search/all/product?q={requests.utils.quote(query)}"
            r = self.session.get(url, timeout=self.timeout)
            if r.status_code != 200:
                return None

            soup = BeautifulSoup(r.text, 'html.parser')
            price_el = soup.find(class_=re.compile(r'price', re.I))
            if price_el:
                m = re.search(r'\$?([\d,]+\.\d{2})', price_el.get_text(strip=True))
                if m:
                    return {
                        'source': 'TCGPlayer',
                        'value': float(m.group(1).replace(',', '')),
                        'url': url
                    }
        except Exception:
            pass
        return None

    def search_ebay_sold(self, card_name: str, set_name: str = None) -> Optional[Dict]:
        """Search eBay sold listings (most reliable for real value)."""
        try:
            query = card_name + (f" {set_name}" if set_name else "") + " card"
            url = (f"https://www.ebay.com/sch/i.html?_nkw={requests.utils.quote(query)}"
                   f"&LH_Sold=1&LH_Complete=1&_ipg=240")

            r = self.session.get(url, timeout=self.timeout)
            if r.status_code != 200:
                return None

            soup = BeautifulSoup(r.text, 'html.parser')
            prices = []
            for el in soup.select('.s-item__price'):
                for m in re.finditer(r'\$([\d,]+\.\d{2})', el.get_text(strip=True)):
                    try:
                        prices.append(float(m.group(1).replace(',', '')))
                    except ValueError:
                        pass

            if prices:
                prices.sort()
                # Use middle 50% to reduce outlier effect
                trimmed = prices[len(prices)//4 : max(len(prices)*3//4, 1)] or prices
                return {
                    'source': 'eBay (sold)',
                    'value': round(sum(trimmed) / len(trimmed), 2),
                    'url': url
                }
        except Exception:
            pass
        return None

    def search_pricecharting(self, card_name: str, set_name: str = None) -> Optional[Dict]:
        """Search PriceCharting."""
        try:
            query = card_name + (f" {set_name}" if set_name else "")
            url = f"https://www.pricecharting.com/search-products?q={requests.utils.quote(query)}&type=prices"

            r = self.session.get(url, timeout=self.timeout)
            if r.status_code != 200:
                return None

            soup = BeautifulSoup(r.text, 'html.parser')
            cell = soup.find('td', class_=re.compile(r'price|used_price'))
            if cell:
                m = re.search(r'\$([\d,]+\.\d{2})', cell.get_text())
                if m:
                    return {
                        'source': 'PriceCharting',
                        'value': float(m.group(1).replace(',', '')),
                        'url': url
                    }
        except Exception:
            pass
        return None

    def fetch_all_values(self, card_name: str, set_name: str = None) -> List[Dict]:
        """Fetch prices from all sources in parallel."""
        sources = [self.search_tcgplayer, self.search_ebay_sold, self.search_pricecharting]
        results = []

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(fn, card_name, set_name) for fn in sources]
            for future in futures:
                try:
                    result = future.result(timeout=15)
                    if result and result.get('value', 0) > 0:
                        results.append(result)
                except Exception:
                    pass

        return results

    def compute_estimate(self, values: List[Dict], condition_score: float = 85.0) -> float:
        """Compute condition-adjusted estimated value."""
        if not values:
            return 0.0

        prices = sorted(v['value'] for v in values)
        median = prices[len(prices) // 2]

        # Condition multiplier (0.6x to 1.3x)
        multiplier = max(0.6, min(1.3, condition_score / 85.0))
        return round(median * multiplier, 2)
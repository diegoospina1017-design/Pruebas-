"""
Keepa API client for auto-fetching Amazon product data.

Setup:
    1. Sign up at https://keepa.com/#!api (trial gratis 7 dias, luego $19/mes)
    2. Copy your API key from https://keepa.com/#!api
    3. Set env var: export KEEPA_API_KEY="tu-clave-aqui"

Endpoints used:
    GET /search?key=KEY&type=product&term=QUERY&domain=1    (1 token)
    GET /product?key=KEY&domain=1&asin=ASIN&stats=90        (~5 tokens)

Token budget on basic plan: ~60,000/month. Plenty for 1,000+ analyses.
"""

import gzip
import io
import json
import os
import re
import time
import urllib.parse
import urllib.request
import urllib.error
import zlib
from dataclasses import dataclass
from typing import List, Optional, Tuple

KEEPA_BASE = "https://api.keepa.com"
DOMAIN_US = 1
DEFAULT_TIMEOUT = 20

CATEGORY_MAP = {
    "Kitchen": "kitchen",
    "Home": "home_garden",
    "Home & Kitchen": "kitchen",
    "Garden": "lawn_garden",
    "Lawn & Garden": "lawn_garden",
    "Beauty": "beauty",
    "Health & Personal Care": "health_personal_care",
    "Health and Beauty": "health_personal_care",
    "Toy": "toys_games",
    "Toys & Games": "toys_games",
    "Sports": "sports",
    "Sports & Outdoors": "sports",
    "Tools & Home Improvement": "tools_home_improvement",
    "Hardware": "tools_home_improvement",
    "Office Product": "office_products",
    "Office Products": "office_products",
    "Pet Products": "pet_supplies",
    "Pet Supplies": "pet_supplies",
    "Apparel": "clothing",
    "Shoes": "shoes_handbags",
    "Baby Product": "baby",
    "Baby": "baby",
    "Grocery": "grocery",
    "Grocery & Gourmet Food": "grocery",
    "Automotive": "automotive",
    "Electronics": "consumer_electronics",
    "Consumer Electronics": "consumer_electronics",
    "PC": "computers",
    "Personal Computer": "computers",
    "Book": "books",
    "Music": "music",
    "Video Games": "video_games",
    "Watch": "watches",
    "Jewelry": "jewelry",
    "Musical Instruments": "musical_instruments",
    "Luggage": "luggage",
}


@dataclass
class KeepaProduct:
    asin: str
    title: str
    current_price: Optional[float]
    avg90_price: Optional[float]
    current_bsr: Optional[int]
    avg90_bsr: Optional[int]
    weight_lb: Optional[float]
    length_in: Optional[float]
    width_in: Optional[float]
    height_in: Optional[float]
    category: str
    product_group: str
    fba_offer_count: Optional[int]
    review_count: Optional[int]
    rating: Optional[float]
    tokens_left: Optional[int]
    raw: dict


class KeepaError(Exception):
    pass


class KeepaClient:
    def __init__(self, api_key: Optional[str] = None, min_request_interval: float = 0.7):
        self.api_key = api_key or os.environ.get("KEEPA_API_KEY")
        if not self.api_key:
            raise KeepaError(
                "Missing Keepa API key. Set KEEPA_API_KEY env var or pass api_key= "
                "(get one at https://keepa.com/#!api)"
            )
        self._last_request_ts = 0.0
        self._min_interval = min_request_interval
        self.tokens_left: Optional[int] = None

    def _throttle(self):
        elapsed = time.time() - self._last_request_ts
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request_ts = time.time()

    def _get(self, path: str, params: dict) -> dict:
        self._throttle()
        params["key"] = self.api_key
        url = f"{KEEPA_BASE}{path}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers={
            "Accept-Encoding": "gzip, deflate",
            "User-Agent": "deal-hunter/1.0",
        })
        try:
            with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT) as r:
                raw = r.read()
                encoding = (r.headers.get("Content-Encoding") or "").lower()
                if encoding == "gzip":
                    raw = gzip.decompress(raw)
                elif encoding == "deflate":
                    raw = zlib.decompress(raw)
                data = json.loads(raw.decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read()
            try:
                if (e.headers.get("Content-Encoding") or "").lower() == "gzip":
                    body = gzip.decompress(body)
            except Exception:
                pass
            body_str = body.decode("utf-8", errors="replace")[:300]
            raise KeepaError(f"HTTP {e.code} from Keepa: {body_str}")
        except urllib.error.URLError as e:
            raise KeepaError(f"Network error reaching Keepa: {e.reason}")

        self.tokens_left = data.get("tokensLeft")
        if "error" in data:
            raise KeepaError(f"Keepa error: {data['error']}")
        return data

    def search(self, query: str, limit: int = 5) -> List["KeepaProduct"]:
        """
        Search Amazon by text. Returns parsed product objects.

        Keepa's /search endpoint with type=product returns FULL product data
        in the response (no separate /product call needed). Costs ~10 tokens
        per search regardless of how many products come back.
        """
        data = self._get("/search", {"type": "product", "term": query, "domain": DOMAIN_US})
        products = data.get("products") or []
        parsed = []
        for p in products[:limit]:
            try:
                parsed.append(self._parse_product(p))
            except Exception as e:
                print(f"  [keepa] failed to parse product: {e}")
        return parsed

    def product(self, asin: str, days: int = 90) -> Optional[KeepaProduct]:
        """Fetch product details + stats. Returns None if not found."""
        data = self._get("/product", {
            "domain": DOMAIN_US,
            "asin": asin,
            "stats": days,
            "offers": 20,
        })
        products = data.get("products") or []
        if not products:
            return None
        return self._parse_product(products[0])

    def _parse_product(self, p: dict) -> KeepaProduct:
        stats = p.get("stats") or {}
        current = stats.get("current") or []
        avg90 = stats.get("avg90") or []

        cur_price = self._cents_to_dollars(current[0] if len(current) > 0 else None)
        avg_price = self._cents_to_dollars(avg90[0] if len(avg90) > 0 else None)

        cur_bsr = current[3] if len(current) > 3 and current[3] > 0 else None
        avg_bsr = avg90[3] if len(avg90) > 3 and avg90[3] > 0 else None

        weight_g = p.get("packageWeight") or p.get("itemWeight")
        weight_lb = (weight_g * 0.00220462) if weight_g else None

        dims_mm = p.get("packageDimensions") or p.get("itemDimensions") or []
        if isinstance(dims_mm, list) and len(dims_mm) >= 3 and all(d for d in dims_mm[:3]):
            length_in, width_in, height_in = [d / 25.4 for d in dims_mm[:3]]
        else:
            length_in = width_in = height_in = None

        product_group = p.get("productGroup", "") or ""
        category = self._map_category(product_group, p.get("categoryTree") or [])

        offer_count_fba = None
        if isinstance(stats.get("offerCountFBA"), list) and stats["offerCountFBA"]:
            v = stats["offerCountFBA"][-1] if isinstance(stats["offerCountFBA"], list) else stats["offerCountFBA"]
            offer_count_fba = v if isinstance(v, int) and v >= 0 else None
        elif isinstance(stats.get("offerCountFBA"), int):
            offer_count_fba = stats["offerCountFBA"]

        return KeepaProduct(
            asin=p.get("asin", ""),
            title=p.get("title", ""),
            current_price=cur_price,
            avg90_price=avg_price,
            current_bsr=cur_bsr,
            avg90_bsr=avg_bsr,
            weight_lb=round(weight_lb, 2) if weight_lb else None,
            length_in=round(length_in, 2) if length_in else None,
            width_in=round(width_in, 2) if width_in else None,
            height_in=round(height_in, 2) if height_in else None,
            category=category,
            product_group=product_group,
            fba_offer_count=offer_count_fba,
            review_count=p.get("reviewCount"),
            rating=(p.get("rating") / 10.0) if p.get("rating") else None,
            tokens_left=self.tokens_left,
            raw=p,
        )

    @staticmethod
    def _cents_to_dollars(v) -> Optional[float]:
        if v is None or v == -1 or v == -2:
            return None
        try:
            return round(int(v) / 100.0, 2)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _map_category(product_group: str, category_tree: List[dict]) -> str:
        if product_group in CATEGORY_MAP:
            return CATEGORY_MAP[product_group]
        for node in category_tree:
            name = node.get("name", "")
            for key, val in CATEGORY_MAP.items():
                if key.lower() in name.lower():
                    return val
        return "default"


def _tokenize(s: str) -> set:
    return set(re.findall(r"\b\w+\b", s.lower())) - {
        "the", "a", "an", "and", "or", "for", "with", "of", "in", "on", "at",
        "pack", "set", "new", "free", "shipping", "store", "pickup",
    }


def match_score(deal_title: str, keepa_product: KeepaProduct, deal_price: Optional[float]) -> float:
    """
    Score how likely this Keepa result is the right match for a deal.
    Higher = better. Uses title overlap + price reasonableness.
    """
    if not keepa_product.title:
        return 0.0

    deal_tokens = _tokenize(deal_title)
    prod_tokens = _tokenize(keepa_product.title)
    if not deal_tokens:
        return 0.0
    overlap = len(deal_tokens & prod_tokens) / len(deal_tokens)
    score = overlap * 60

    if deal_price and keepa_product.current_price:
        ratio = keepa_product.current_price / deal_price
        if 1.3 <= ratio <= 4.0:
            score += 25
        elif 1.0 <= ratio < 1.3:
            score += 10
        elif ratio > 4.0:
            score += 5

    if keepa_product.review_count and keepa_product.review_count > 50:
        score += 10
    if keepa_product.avg90_bsr and keepa_product.avg90_bsr < 100_000:
        score += 5

    return round(score, 1)


def find_best_match(
    client: KeepaClient,
    deal_title: str,
    deal_price: Optional[float],
    candidates_to_inspect: int = 3,
) -> Tuple[Optional[KeepaProduct], List[Tuple[KeepaProduct, float]]]:
    """
    Search + rank Keepa candidates for a deal in a single API call.

    Returns (best_match, all_ranked) where all_ranked is a list of
    (product, score) tuples in descending score order.
    """
    products = client.search(deal_title, limit=candidates_to_inspect)
    if not products:
        return None, []

    ranked = [(p, match_score(deal_title, p, deal_price)) for p in products]
    ranked.sort(key=lambda x: x[1], reverse=True)
    best = ranked[0][0] if ranked and ranked[0][1] >= 40 else None
    return best, ranked


if __name__ == "__main__":
    import sys
    if "KEEPA_API_KEY" not in os.environ:
        print("Set KEEPA_API_KEY env var first. Example:")
        print('  export KEEPA_API_KEY="your-key-here"')
        sys.exit(1)

    client = KeepaClient()
    query = sys.argv[1] if len(sys.argv) > 1 else "Pyrex 8-piece glass food storage"
    deal_price = float(sys.argv[2]) if len(sys.argv) > 2 else None

    print(f"Searching Keepa for: {query!r}")
    best, ranked = find_best_match(client, query, deal_price)
    print(f"Tokens left: {client.tokens_left}")
    print(f"\nTop {len(ranked)} candidates:")
    for prod, score in ranked:
        marker = " <-- BEST" if best and prod.asin == best.asin else ""
        print(f"  [{score:5.1f}] {prod.asin}  ${prod.current_price}  "
              f"BSR {prod.avg90_bsr}  {prod.title[:60]}{marker}")

"""
Bridges filtered deals to the profit calculator.

Two ways to supply Amazon-side data:

1. Manual: edit asin_map.json with entries keyed by deal URL.
2. Auto: pass a KeepaClient instance - analyzer searches Keepa for each
   deal and caches the best match back into asin_map (so re-runs are free).

asin_map entry shape:
{
  "https://...": {
    "asin": "B07ABC123",
    "amazon_sale_price": 24.99,
    "weight_lb": 0.8,
    "length_in": 10, "width_in": 8, "height_in": 4,
    "category": "kitchen",
    "size_tier": "standard",
    "units_per_box": 24,
    "bsr": 32000,
    "fba_sellers": 8,
    "_source": "keepa" | "manual",
    "_match_score": 78.5,
    "_alternatives": [{"asin": "...", "score": ...}, ...]
  }
}
"""

import os
import sys
from typing import List, Optional

CALC_PATH = os.path.join(os.path.dirname(__file__), "..", "calculator")
sys.path.insert(0, os.path.abspath(CALC_PATH))

from profit import ProductInput, calculate

try:
    from sources.keepa import KeepaClient, KeepaError, find_best_match
except ImportError:
    KeepaClient = None
    KeepaError = Exception


def _pick_size_tier(weight_lb: Optional[float], length_in, width_in, height_in) -> str:
    if not weight_lb or not (length_in and width_in and height_in):
        return "standard"
    dims = sorted([length_in, width_in, height_in], reverse=True)
    if weight_lb <= 1.0 and dims[0] <= 15 and dims[1] <= 12 and dims[2] <= 0.75:
        return "small_standard"
    if weight_lb <= 20 and dims[0] <= 18:
        return "standard"
    return "large_bulky"


def keepa_lookup(
    deal: dict,
    keepa: "KeepaClient",
    candidates: int = 3,
) -> Optional[dict]:
    """Run a Keepa search for this deal and return an asin_map-shaped dict."""
    title = deal.get("title", "")
    if not title:
        return None
    try:
        best, ranked = find_best_match(keepa, title, deal.get("deal_price"), candidates)
    except KeepaError as e:
        print(f"  [keepa] error for {title[:40]!r}: {e}")
        return None

    if not best:
        if not ranked:
            return None
        print(f"  [keepa] no high-confidence match for {title[:50]!r} "
              f"(top score {ranked[0][1]:.0f}) - flagging as low-confidence")

    chosen = best or ranked[0][0]
    chosen_score = next((s for p, s in ranked if p.asin == chosen.asin), 0)

    if not chosen.weight_lb or not chosen.length_in:
        print(f"  [keepa] {chosen.asin} missing dimensions/weight - using defaults")

    weight = chosen.weight_lb or 1.0
    length = chosen.length_in or 8.0
    width = chosen.width_in or 6.0
    height = chosen.height_in or 4.0

    sale_price = chosen.avg90_price or chosen.current_price
    if not sale_price:
        return None

    return {
        "asin": chosen.asin,
        "amazon_sale_price": sale_price,
        "weight_lb": weight,
        "length_in": length,
        "width_in": width,
        "height_in": height,
        "category": chosen.category,
        "size_tier": _pick_size_tier(weight, length, width, height),
        "units_per_box": 12,
        "bsr": chosen.avg90_bsr or chosen.current_bsr,
        "fba_sellers": chosen.fba_offer_count,
        "_source": "keepa",
        "_match_score": chosen_score,
        "_keepa_title": chosen.title,
        "_alternatives": [
            {"asin": p.asin, "score": s, "price": p.current_price, "title": p.title[:60]}
            for p, s in ranked if p.asin != chosen.asin
        ][:3],
    }


def analyze_deal(deal: dict, amazon_data: Optional[dict]) -> dict:
    out = {**deal}

    if not amazon_data:
        out["_analysis"] = {
            "status": "needs_amazon_lookup",
            "instructions": (
                "Set KEEPA_API_KEY for auto-lookup, OR add a manual entry "
                "to asin_map.json with weight, dimensions, Amazon price, category."
            ),
        }
        return out

    cost = deal.get("deal_price")
    if cost is None:
        out["_analysis"] = {"status": "no_cost_price"}
        return out

    sales_tax_pct = amazon_data.get("sales_tax_pct", 0.053)
    months = amazon_data.get("months_in_storage", 1.5)
    peak = amazon_data.get("peak_season", False)

    product = ProductInput(
        name=deal.get("title", "Unknown")[:60],
        cost_per_unit=cost,
        sale_price=amazon_data["amazon_sale_price"],
        weight_lb=amazon_data["weight_lb"],
        length_in=amazon_data["length_in"],
        width_in=amazon_data["width_in"],
        height_in=amazon_data["height_in"],
        category=amazon_data.get("category", "default"),
        size_tier=amazon_data.get("size_tier", "standard"),
        units_per_box=amazon_data.get("units_per_box", 12),
        sales_tax_pct=sales_tax_pct,
        months_in_storage=months,
        peak_season=peak,
    )
    breakdown = calculate(product)

    bsr = amazon_data.get("bsr")
    fba_sellers = amazon_data.get("fba_sellers")
    warnings = []
    if bsr is not None and bsr > 100_000:
        warnings.append(f"BSR {bsr:,} is above 100K (slow seller)")
    if fba_sellers is not None and fba_sellers > 20:
        warnings.append(f"{fba_sellers} FBA sellers - price war risk")
    if amazon_data.get("_source") == "keepa" and amazon_data.get("_match_score", 100) < 40:
        warnings.append(f"low Keepa match confidence ({amazon_data['_match_score']:.0f}/100) - verify ASIN manually")

    out["_analysis"] = {
        "status": "analyzed",
        "asin": amazon_data.get("asin"),
        "amazon_sale_price": amazon_data["amazon_sale_price"],
        "net_profit": round(breakdown.net_profit, 2),
        "margin_pct": round(breakdown.margin_pct, 1),
        "roi_pct": round(breakdown.roi_pct, 1),
        "recommendation": breakdown.recommendation,
        "warnings": warnings,
        "data_source": amazon_data.get("_source", "manual"),
        "match_score": amazon_data.get("_match_score"),
        "keepa_title": amazon_data.get("_keepa_title"),
        "alternatives": amazon_data.get("_alternatives", []),
        "fee_breakdown": {
            "referral": round(breakdown.referral_fee, 2),
            "fba_fulfillment": round(breakdown.fba_fee, 2),
            "storage": round(breakdown.storage_fee, 2),
            "inbound_shipping": round(breakdown.inbound_shipping, 2),
            "prep_supplies": round(breakdown.supplies, 2),
        },
    }
    return out


def analyze_all(
    deals: List[dict],
    asin_map: dict,
    keepa: Optional["KeepaClient"] = None,
) -> List[dict]:
    analyzed = []
    for d in deals:
        url = d.get("url", "")
        amazon_data = asin_map.get(url)

        if not amazon_data and keepa:
            print(f"  [keepa] searching: {d.get('title', '')[:60]!r}")
            amazon_data = keepa_lookup(d, keepa)
            if amazon_data:
                asin_map[url] = amazon_data
                ts_left = keepa.tokens_left
                if ts_left is not None:
                    print(f"  [keepa] matched {amazon_data['asin']} "
                          f"(score {amazon_data.get('_match_score', 0):.0f}, "
                          f"tokens left {ts_left})")

        analyzed.append(analyze_deal(d, amazon_data))
    return analyzed

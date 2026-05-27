"""
Bridges filtered deals to the profit calculator.

For each candidate deal you can optionally provide Amazon-side data
(ASIN, sale price, weight, dimensions, category) via an asin_map.json file:

{
  "https://example.com/deal/1": {
    "asin": "B07ABC123",
    "amazon_sale_price": 24.99,
    "weight_lb": 0.8,
    "length_in": 10, "width_in": 8, "height_in": 4,
    "category": "kitchen",
    "size_tier": "standard",
    "units_per_box": 24,
    "bsr": 32000,
    "fba_sellers": 8
  }
}

When the map has an entry for a deal URL, analyzer runs the full profit
calculation. Otherwise the deal is returned without Amazon data and gets
flagged "needs manual lookup".
"""

import os
import sys
from typing import List, Optional

CALC_PATH = os.path.join(os.path.dirname(__file__), "..", "calculator")
sys.path.insert(0, os.path.abspath(CALC_PATH))

from profit import ProductInput, calculate, ProfitBreakdown


def analyze_deal(deal: dict, amazon_data: Optional[dict]) -> dict:
    out = {**deal}

    if not amazon_data:
        out["_analysis"] = {
            "status": "needs_amazon_lookup",
            "instructions": (
                "Open the deal URL, find matching product on Amazon, copy the ASIN. "
                "Then add an entry to asin_map.json with weight, dimensions, "
                "Amazon price, category."
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
        warnings.append(f"BSR {bsr:,} is above 100K threshold (slow seller)")
    if fba_sellers is not None and fba_sellers > 20:
        warnings.append(f"{fba_sellers} FBA sellers - high price war risk")

    out["_analysis"] = {
        "status": "analyzed",
        "asin": amazon_data.get("asin"),
        "amazon_sale_price": amazon_data["amazon_sale_price"],
        "net_profit": round(breakdown.net_profit, 2),
        "margin_pct": round(breakdown.margin_pct, 1),
        "roi_pct": round(breakdown.roi_pct, 1),
        "recommendation": breakdown.recommendation,
        "warnings": warnings,
        "fee_breakdown": {
            "referral": round(breakdown.referral_fee, 2),
            "fba_fulfillment": round(breakdown.fba_fee, 2),
            "storage": round(breakdown.storage_fee, 2),
            "inbound_shipping": round(breakdown.inbound_shipping, 2),
            "prep_supplies": round(breakdown.supplies, 2),
        },
    }
    return out


def analyze_all(deals: List[dict], asin_map: dict) -> List[dict]:
    analyzed = []
    for d in deals:
        amazon_data = asin_map.get(d.get("url", ""))
        analyzed.append(analyze_deal(d, amazon_data))
    return analyzed

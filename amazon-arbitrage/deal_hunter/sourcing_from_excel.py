"""
Sourcing from Keepa Excel exports - zero tokens needed.

When you export a "Best Sellers List" from Keepa with full columns enabled,
the Excel already contains everything we need: title, brand, current/avg
prices, BSR, FBA fee, referral %, return rate, FBA seller count, buy-box
share by Amazon, etc. This script reads that directly - no API calls.

Usage:
    python3 sourcing_from_excel.py sports_outdoors_keepa.xlsx
    python3 sourcing_from_excel.py pet_supplies_keepa.xlsx --target-roi 40
    python3 sourcing_from_excel.py file.xlsx --max-bb-amazon 0.3
"""

import argparse
import json
import math
import os
import sys
from dataclasses import dataclass
from typing import Optional

try:
    import openpyxl
except ImportError:
    print("openpyxl not installed. Install with: pip3 install openpyxl")
    sys.exit(1)

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "calculator")))

from shipping import avg_inbound_shipping, supplies_cost_per_unit

VA_SALES_TAX = 0.060
GRAMS_TO_LB = 0.00220462
CM3_TO_IN3 = 0.0610237
STORAGE_RATE_STANDARD = 0.78  # $/cubic foot/month off-peak
STORAGE_RATE_OVERSIZE = 0.56
PEAK_MULTIPLIER = 3.07  # Q4 storage roughly 3x


@dataclass
class KeepaRow:
    asin: str
    title: str
    brand: str
    category: str
    sale_price: Optional[float]
    bsr: Optional[int]
    weight_lb: Optional[float]
    volume_in3: Optional[float]
    fba_fee: Optional[float]
    referral_pct: Optional[float]
    return_rate: Optional[str]
    rating: Optional[float]
    fba_sellers: Optional[int]
    bb_pct_amazon: Optional[float]
    is_hazmat: bool
    is_adult: bool


def _f(v):
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _i(v):
    f = _f(v)
    return int(f) if f is not None else None


def _yes(v) -> bool:
    return isinstance(v, str) and v.strip().lower() == "yes"


def load_excel(path: str) -> list:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []
    headers = rows[0]
    idx = {h: i for i, h in enumerate(headers) if h}

    def col(row, key):
        return row[idx[key]] if key in idx and idx[key] < len(row) else None

    results = []
    for row in rows[1:]:
        if not col(row, "ASIN"):
            continue
        weight_g = _f(col(row, "Package: Weight (g)"))
        volume_cm3 = _f(col(row, "Package: Dimension (cm³)"))
        results.append(KeepaRow(
            asin=col(row, "ASIN"),
            title=(col(row, "Title") or "")[:120],
            brand=col(row, "Brand") or "",
            category=col(row, "Categories: Tree") or "",
            sale_price=_f(col(row, "Buy Box: 90 days avg.")) or _f(col(row, "Amazon: 90 days avg.")),
            bsr=_i(col(row, "Sales Rank: 90 days avg.")),
            weight_lb=round(weight_g * GRAMS_TO_LB, 3) if weight_g else None,
            volume_in3=round(volume_cm3 * CM3_TO_IN3, 1) if volume_cm3 else None,
            fba_fee=_f(col(row, "FBA Pick&Pack Fee")),
            referral_pct=_f(col(row, "Referral Fee %")),
            return_rate=col(row, "Return Rate"),
            rating=_f(col(row, "Reviews: Rating")),
            fba_sellers=_i(col(row, "New FBA Offer Count: 90 days avg.")),
            bb_pct_amazon=_f(col(row, "Buy Box: % Amazon 90 days")),
            is_hazmat=_yes(col(row, "Is HazMat")),
            is_adult=_yes(col(row, "Adult Product")),
        ))
    return results


def storage_per_unit(volume_in3: Optional[float], peak: bool = False) -> float:
    if not volume_in3:
        return 0.10
    cubic_feet = volume_in3 / 1728
    rate = STORAGE_RATE_STANDARD * (PEAK_MULTIPLIER if peak else 1.0)
    return cubic_feet * rate * 1.5  # ~1.5 months avg


def max_buy_price(
    sale_price: float,
    fba_fee: float,
    referral_pct: float,
    weight_lb: float,
    volume_in3: Optional[float],
    units_per_box: int,
    target_roi: float,
    target_profit: float,
    sales_tax_pct: float = VA_SALES_TAX,
    peak_season: bool = False,
) -> float:
    """Binary search the highest cost-per-unit satisfying both target_profit and target_roi."""
    referral = max(0.30, sale_price * referral_pct)
    storage = storage_per_unit(volume_in3, peak_season)
    inbound = avg_inbound_shipping(weight_lb, units_per_box, True)
    supplies = supplies_cost_per_unit(units_per_box)

    fixed_amazon = referral + fba_fee + storage
    fixed_landed = inbound + supplies

    def profit_and_roi(cogs):
        landed = cogs * (1 + sales_tax_pct) + fixed_landed
        net = sale_price - landed - fixed_amazon
        roi = net / landed if landed > 0 else 0
        return net, roi

    lo, hi, best = 0.0, sale_price, 0.0
    for _ in range(40):
        mid = (lo + hi) / 2
        net, roi = profit_and_roi(mid)
        if net >= target_profit and roi >= target_roi:
            best = mid
            lo = mid
        else:
            hi = mid
        if hi - lo < 0.005:
            break
    return round(best, 2)


def evaluate(row: KeepaRow, args) -> dict:
    out = {
        "asin": row.asin,
        "title": row.title[:90],
        "brand": row.brand,
        "category": row.category.split("›")[-1].strip() if row.category else "",
        "sale_price": row.sale_price,
        "bsr": row.bsr,
        "weight_lb": row.weight_lb,
        "fba_fee": row.fba_fee,
        "fba_sellers": row.fba_sellers,
        "bb_pct_amazon": row.bb_pct_amazon,
        "return_rate": row.return_rate,
        "rating": row.rating,
        "warnings": [],
        "status": "viable",
    }

    if not row.sale_price or not row.fba_fee or not row.referral_pct:
        out["status"] = "incomplete_data"
        return out

    if row.is_hazmat:
        out["status"] = "hazmat_skip"
        return out
    if row.is_adult:
        out["status"] = "adult_skip"
        return out

    if row.bb_pct_amazon is not None and row.bb_pct_amazon > args.max_bb_amazon:
        out["status"] = "amazon_owns_bb"
        out["warnings"].append(f"Amazon holds buy box {row.bb_pct_amazon*100:.0f}% of time")
        return out

    if row.fba_sellers is not None and row.fba_sellers > args.max_fba_sellers:
        out["warnings"].append(f"{row.fba_sellers} FBA sellers - price war risk")

    if row.rating is not None and row.rating < args.min_rating:
        out["status"] = "low_rating"
        return out

    if row.return_rate and row.return_rate.lower() in ("high", "very high"):
        out["status"] = "high_returns"
        return out

    if row.bsr is not None and row.bsr > args.max_bsr:
        out["status"] = "low_velocity"
        return out

    if row.weight_lb is None:
        row.weight_lb = 1.0
        out["warnings"].append("weight missing - assumed 1lb")

    if row.sale_price < args.min_sale_price:
        out["status"] = "too_cheap"
        return out

    max_cost = max_buy_price(
        sale_price=row.sale_price,
        fba_fee=row.fba_fee,
        referral_pct=row.referral_pct,
        weight_lb=row.weight_lb,
        volume_in3=row.volume_in3,
        units_per_box=args.units_per_box,
        target_roi=args.target_roi / 100.0,
        target_profit=args.target_profit,
    )

    out["max_buy_price"] = max_cost
    out["max_buy_pct"] = round(max_cost / row.sale_price * 100, 1) if row.sale_price else 0

    if max_cost <= 0:
        out["status"] = "not_profitable"
    elif max_cost / row.sale_price < 0.20:
        out["status"] = "very_aggressive_target"
        out["warnings"].append(f"need to buy at <{out['max_buy_pct']:.0f}% of sale - tough")

    return out


def render(results: list, args) -> str:
    by_status = {}
    for r in results:
        by_status.setdefault(r["status"], []).append(r)

    viable = by_status.get("viable", []) + by_status.get("very_aggressive_target", [])
    viable.sort(key=lambda x: (x.get("max_buy_pct") or 0, -1 * (x.get("bsr") or 999999)), reverse=True)

    lines = [
        f"# Sourcing Targets - {os.path.basename(args.excel_file)}",
        f"_Filters: ROI >= {args.target_roi}%, profit >= ${args.target_profit:.2f}, "
        f"max Amazon BB share {args.max_bb_amazon*100:.0f}%, max BSR {args.max_bsr:,}_",
        "",
        f"- Total products in list: **{len(results)}**",
        f"- Viable for sourcing: **{len(viable)}**",
        f"- Amazon dominates buy box: **{len(by_status.get('amazon_owns_bb', []))}**",
        f"- Not profitable: **{len(by_status.get('not_profitable', []))}**",
        f"- Other skips (hazmat/adult/low-rating/slow/cheap): "
        f"**{sum(len(by_status.get(k, [])) for k in ['hazmat_skip','adult_skip','low_rating','high_returns','low_velocity','too_cheap','incomplete_data'])}**",
        "",
    ]

    if viable:
        lines += [
            "## Shopping list",
            "",
            "Find these products at OR BELOW the Max Buy price. They are best sellers "
            "with reasonable competition and demand.",
            "",
            "| # | ASIN | Brand | Product | Amazon $ | BSR | Weight | FBA sellers | BB %Amz | Max Buy | % of sale | Notes |",
            "|---|------|-------|---------|---------:|----:|-------:|------------:|--------:|--------:|----------:|-------|",
        ]
        for i, r in enumerate(viable, 1):
            bsr = f"{r['bsr']:,}" if r.get("bsr") else "?"
            bb_amz = f"{r['bb_pct_amazon']*100:.0f}%" if r.get("bb_pct_amazon") is not None else "?"
            fbas = r.get("fba_sellers") if r.get("fba_sellers") is not None else "?"
            wt = f"{r['weight_lb']:.2f}lb" if r.get("weight_lb") else "?"
            warns = "; ".join(r.get("warnings", []))[:60]
            lines.append(
                f"| {i} | `{r['asin']}` | {r['brand'][:18]} | {r['title'][:60]} "
                f"| ${r['sale_price']:.2f} | {bsr} | {wt} | {fbas} | {bb_amz} "
                f"| **${r['max_buy_price']:.2f}** | {r['max_buy_pct']:.0f}% | {warns} |"
            )

    # Add reason breakdowns
    reasons = {
        "amazon_owns_bb": "Amazon dominates the buy box (cannot compete)",
        "not_profitable": "Fees exceed sale price (heavy/bulky/cheap)",
        "hazmat_skip": "Hazmat - requires special FBA approval",
        "adult_skip": "Adult products - restricted",
        "low_rating": f"Rating below {args.min_rating}",
        "high_returns": "High return rate",
        "low_velocity": f"BSR above {args.max_bsr:,}",
        "too_cheap": f"Sale price below ${args.min_sale_price:.2f}",
        "incomplete_data": "Missing key data in Keepa export",
    }
    for status, label in reasons.items():
        bucket = by_status.get(status, [])
        if not bucket:
            continue
        lines += [
            "",
            f"## Skipped: {label} ({len(bucket)})",
            "",
            "| ASIN | Brand | Product | Amazon $ | Why |",
            "|------|-------|---------|---------:|-----|",
        ]
        for r in bucket[:15]:
            why = r["warnings"][0] if r.get("warnings") else label
            price = f"${r['sale_price']:.2f}" if r.get("sale_price") else "?"
            lines.append(f"| `{r['asin']}` | {r['brand'][:18]} | {r['title'][:55]} | {price} | {why} |")

    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="Process Keepa Excel best-sellers export into a sourcing list")
    parser.add_argument("excel_file", help="Path to Keepa Excel export with all columns enabled")
    parser.add_argument("--target-roi", type=float, default=30.0)
    parser.add_argument("--target-profit", type=float, default=3.0)
    parser.add_argument("--max-bb-amazon", type=float, default=0.40,
                        help="Max fraction of time Amazon owns the buy box (default 0.40 = 40%)")
    parser.add_argument("--max-fba-sellers", type=int, default=15)
    parser.add_argument("--max-bsr", type=int, default=300_000)
    parser.add_argument("--min-rating", type=float, default=4.0)
    parser.add_argument("--min-sale-price", type=float, default=10.0)
    parser.add_argument("--units-per-box", type=int, default=12)
    parser.add_argument("--output-md", default=None)
    parser.add_argument("--output-json", default=None)
    args = parser.parse_args()

    if not os.path.exists(args.excel_file):
        print(f"[error] file not found: {args.excel_file}")
        sys.exit(1)

    base = os.path.splitext(os.path.basename(args.excel_file))[0]
    args.output_md = args.output_md or os.path.join(HERE, f"sourcing_{base}.md")
    args.output_json = args.output_json or os.path.join(HERE, f"sourcing_{base}.json")

    rows = load_excel(args.excel_file)
    print(f"[load] {len(rows)} products from {args.excel_file}")

    results = [evaluate(r, args) for r in rows]
    viable = sum(1 for r in results if r["status"] in ("viable", "very_aggressive_target"))
    print(f"[analyze] {viable} viable, {len(results) - viable} skipped")

    with open(args.output_md, "w", encoding="utf-8") as f:
        f.write(render(results, args))
    with open(args.output_json, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(f"[write] {args.output_md}")
    print(f"[write] {args.output_json}")


if __name__ == "__main__":
    main()

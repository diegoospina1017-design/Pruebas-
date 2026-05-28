"""
Sourcing targets - reverse arbitrage workflow.

Take a list of known-good ASINs (e.g. Keepa best sellers export), fetch Amazon
data via Keepa, and compute the MAX price you can pay for each one to hit
your target ROI. Output: a shopping list you take to Walmart/Target/Ross.

Usage:
    python3 sourcing_targets.py                    # process targets_list.txt with default settings
    python3 sourcing_targets.py --limit 20         # only first 20 ASINs (cheaper, faster)
    python3 sourcing_targets.py --batch-size 10    # ASINs per Keepa call (default 20)
    python3 sourcing_targets.py --target-roi 40    # require 40% ROI instead of 30
    python3 sourcing_targets.py --target-profit 5  # require $5 profit instead of $3
    python3 sourcing_targets.py --dry-run          # show token cost without spending

Tokens consumed: ~1 token per ASIN in the bulk request, plus a small base cost.
For 100 ASINs: budget ~100 tokens (under 2 hours of free-tier refill).
"""

import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "calculator")))

from sources.keepa import KeepaClient, KeepaError, KeepaProduct
from fees import (
    fba_fulfillment_fee, monthly_storage_fee, referral_fee, REFERRAL_FEES,
)
from shipping import avg_inbound_shipping, supplies_cost_per_unit

VA_SALES_TAX = 0.060


def _pick_size_tier(weight_lb, dims):
    if not weight_lb or not all(dims):
        return "standard"
    longest, mid, shortest = sorted(dims, reverse=True)
    if weight_lb <= 1.0 and longest <= 15 and mid <= 12 and shortest <= 0.75:
        return "small_standard"
    if weight_lb <= 20 and longest <= 18:
        return "standard"
    return "large_bulky"


def max_buy_price(
    sale_price: float,
    weight_lb: float,
    length_in: float,
    width_in: float,
    height_in: float,
    category: str,
    size_tier: str,
    units_per_box: int = 12,
    target_roi: float = 0.30,
    target_profit: float = 3.00,
    sales_tax_pct: float = VA_SALES_TAX,
    months_in_storage: float = 1.5,
) -> float:
    """
    Binary-search for the maximum cost-per-unit such that:
      net_profit >= target_profit AND roi >= target_roi.

    Returns 0 if no positive cost satisfies the rules.
    """
    ref = referral_fee(sale_price, category)
    fba = fba_fulfillment_fee(weight_lb, size_tier)
    storage = monthly_storage_fee(length_in, width_in, height_in, size_tier, months_in_storage)
    inbound = avg_inbound_shipping(weight_lb, units_per_box, True)
    supplies = supplies_cost_per_unit(units_per_box)

    fixed_amazon = ref + fba + storage
    fixed_landed = inbound + supplies

    def profit_and_roi(cogs):
        landed_per_unit = cogs * (1 + sales_tax_pct) + fixed_landed
        total_costs = landed_per_unit + fixed_amazon
        net = sale_price - total_costs
        roi = net / landed_per_unit if landed_per_unit > 0 else 0
        return net, roi

    lo, hi = 0.0, sale_price
    best = 0.0
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


def load_asins(path: str, limit: int = 0) -> list:
    asins = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            a = line.strip()
            if a and a.upper() != "ASIN" and len(a) >= 10:
                asins.append(a)
    return asins[:limit] if limit > 0 else asins


def analyze_target(p: KeepaProduct, target_roi: float, target_profit: float) -> dict:
    sale_price = p.avg90_price or p.current_price
    if not sale_price:
        return {"asin": p.asin, "title": p.title, "status": "no_price"}

    weight = p.weight_lb or 1.0
    length = p.length_in or 8.0
    width = p.width_in or 6.0
    height = p.height_in or 4.0
    size_tier = _pick_size_tier(weight, [length, width, height])

    max_cost = max_buy_price(
        sale_price=sale_price,
        weight_lb=weight,
        length_in=length, width_in=width, height_in=height,
        category=p.category,
        size_tier=size_tier,
        target_roi=target_roi / 100.0,
        target_profit=target_profit,
    )

    return {
        "asin": p.asin,
        "title": (p.title or "?")[:90],
        "category": p.category,
        "amazon_price": sale_price,
        "current_price": p.current_price,
        "avg90_price": p.avg90_price,
        "bsr_avg90": p.avg90_bsr,
        "bsr_current": p.current_bsr,
        "weight_lb": round(weight, 2),
        "dimensions": f"{length:.1f}x{width:.1f}x{height:.1f}",
        "size_tier": size_tier,
        "max_buy_price": max_cost,
        "max_buy_pct": round(max_cost / sale_price * 100, 1) if sale_price else 0,
        "review_count": p.review_count,
        "rating": p.rating,
        "fba_sellers": p.fba_offer_count,
        "status": "viable" if max_cost > 0 else "not_profitable",
    }


def render_markdown(results: list, target_roi: float, target_profit: float) -> str:
    viable = [r for r in results if r.get("status") == "viable"]
    no_price = [r for r in results if r.get("status") == "no_price"]
    not_profit = [r for r in results if r.get("status") == "not_profitable"]

    viable.sort(key=lambda x: (x["max_buy_pct"], -1 * (x["bsr_avg90"] or 999999)), reverse=True)

    lines = [
        "# Sourcing Targets Report",
        f"_Target: \\u2265 {target_roi}% ROI and \\u2265 ${target_profit:.2f} profit per unit_",
        "",
        f"- Total ASINs analyzed: **{len(results)}**",
        f"- Viable (can be sourced profitably): **{len(viable)}**",
        f"- Not profitable at any positive price: **{len(not_profit)}**",
        f"- Missing price data: **{len(no_price)}**",
        "",
        "## Shopping list - target prices",
        "",
        "When you find any of these products at or below the **Max buy** column,"
        " buy them. Best to verify ASIN restrictions in Amazon Seller App first.",
        "",
        "| # | ASIN | Product | Amazon $ | BSR (90d) | Weight | Max buy | % of sale |",
        "|---|------|---------|---------:|----------:|-------:|--------:|----------:|",
    ]
    for i, r in enumerate(viable, 1):
        bsr = f"{r['bsr_avg90']:,}" if r['bsr_avg90'] else "?"
        lines.append(
            f"| {i} | `{r['asin']}` | {r['title']} "
            f"| ${r['amazon_price']:.2f} | {bsr} | {r['weight_lb']}lb "
            f"| **${r['max_buy_price']:.2f}** | {r['max_buy_pct']:.0f}% |"
        )

    if not_profit:
        lines.extend([
            "",
            "## Not profitable",
            "_These would lose money even at a $0.01 buy price (usually due to huge",
            " FBA fees on bulky items or very low Amazon sale prices)._",
            "",
            "| ASIN | Product | Amazon $ | Weight |",
            "|------|---------|---------:|-------:|",
        ])
        for r in not_profit[:20]:
            lines.append(
                f"| `{r['asin']}` | {r['title']} "
                f"| ${r['amazon_price']:.2f} | {r['weight_lb']}lb |"
            )

    if no_price:
        lines.extend([
            "",
            "## Missing price data (skip or re-fetch later)",
            "",
        ])
        for r in no_price:
            lines.append(f"- `{r['asin']}` - {r['title']}")

    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="Sourcing targets - reverse arbitrage from ASIN list")
    parser.add_argument("--asin-file", default=os.path.join(HERE, "targets_list.txt"))
    parser.add_argument("--limit", type=int, default=0, help="Process only first N ASINs (0 = all)")
    parser.add_argument("--batch-size", type=int, default=20, help="ASINs per Keepa call")
    parser.add_argument("--target-roi", type=float, default=30.0, help="Required ROI percent")
    parser.add_argument("--target-profit", type=float, default=3.0, help="Required net profit per unit ($)")
    parser.add_argument("--output", default=os.path.join(HERE, "sourcing_report.md"))
    parser.add_argument("--output-json", default=os.path.join(HERE, "sourcing_targets.json"))
    parser.add_argument("--dry-run", action="store_true", help="Show token estimate without API calls")
    parser.add_argument("--wait-between-batches", type=float, default=0,
                        help="Seconds to wait between batches (for low token budgets)")
    args = parser.parse_args()

    asins = load_asins(args.asin_file, args.limit)
    print(f"[load] {len(asins)} ASINs from {args.asin_file}")

    if args.dry_run:
        est_tokens = len(asins) + (len(asins) // args.batch_size + 1) * 2
        print(f"[estimate] ~{est_tokens} tokens (roughly 1/ASIN + small base per batch)")
        return

    try:
        client = KeepaClient()
    except KeepaError as e:
        print(f"[keepa] {e}")
        sys.exit(1)

    all_results = []
    for i in range(0, len(asins), args.batch_size):
        batch = asins[i:i + args.batch_size]
        print(f"[batch {i // args.batch_size + 1}] fetching {len(batch)} ASINs...")
        try:
            products = client.products_bulk(batch)
        except KeepaError as e:
            print(f"  failed: {e}")
            if "tokens" in str(e).lower() or "rate" in str(e).lower():
                print("  hit a token/rate limit - try again later or use --limit")
                break
            continue

        for p in products:
            r = analyze_target(p, args.target_roi, args.target_profit)
            all_results.append(r)

        if client.tokens_left is not None:
            print(f"  tokens left: {client.tokens_left}")

        if args.wait_between_batches and i + args.batch_size < len(asins):
            print(f"  sleeping {args.wait_between_batches}s...")
            time.sleep(args.wait_between_batches)

    report = render_markdown(all_results, args.target_roi, args.target_profit)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(report)
    with open(args.output_json, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2)

    viable_count = sum(1 for r in all_results if r.get("status") == "viable")
    print(f"\n[done] {len(all_results)} analyzed, {viable_count} viable for sourcing")
    print(f"[write] {args.output}")
    print(f"[write] {args.output_json}")


if __name__ == "__main__":
    main()

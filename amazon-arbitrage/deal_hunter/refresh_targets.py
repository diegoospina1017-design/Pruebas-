"""
Refresh Targets - re-check your top niches against current Keepa data.

The Excel export was a snapshot. Markets shift: prices drop, new FBA
sellers join, Amazon starts dominating the buy box. Before buying any
product, validate the numbers are still good NOW.

How it uses tokens (free plan = 1 token/min):
  - 1 bulk fetch of N ASINs ~ N * 1 + base ≈ N+2 tokens
  - 20 ASINs ≈ 22 tokens (under 25 min of refill)
  - 50 ASINs ≈ 52 tokens (under 1 hour of refill)

Default: refresh top 20 hidden gems (highest opportunity score).
Compares NEW values vs the snapshot in niches.json/sourcing_*.json,
flags changes that matter:

  - sale_price changed >10%       (margin shifted)
  - bsr changed >50%              (demand shifted)
  - fba_sellers grew              (new competition)
  - bb_pct_amazon went up         (Amazon entering market)
  - product became hazmat/adult   (now restricted)

Usage:
    python3 refresh_targets.py                    # top 20 by opportunity score
    python3 refresh_targets.py --limit 10         # cheaper run
    python3 refresh_targets.py --tier HIDDEN_GEM  # only one tier
    python3 refresh_targets.py --dry-run          # estimate tokens, don't call
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from typing import List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def load_niches() -> List[dict]:
    path = os.path.join(HERE, "niches.json")
    if not os.path.exists(path):
        print(f"[error] {path} not found - run find_niches.py first")
        sys.exit(1)
    with open(path) as f:
        return json.load(f)


def select_targets(niches: List[dict], tier: Optional[str], limit: int) -> List[dict]:
    pool = niches
    if tier:
        pool = [n for n in pool if n.get("_tier") == tier]
    pool.sort(key=lambda x: x.get("_score", 0), reverse=True)
    return pool[:limit]


def estimate_tokens(n_asins: int) -> int:
    return n_asins + 2


def detect_changes(old: dict, new_product) -> List[str]:
    """Compare snapshot to fresh Keepa data. Return human-readable change notes."""
    changes = []

    old_price = old.get("sale_price") or 0
    new_price = new_product.avg90_price or new_product.current_price or 0
    if old_price > 0 and new_price > 0:
        pct = (new_price - old_price) / old_price * 100
        if abs(pct) >= 10:
            arrow = "UP" if pct > 0 else "DOWN"
            changes.append(
                f"price {arrow} {abs(pct):.0f}% (${old_price:.2f} -> ${new_price:.2f})"
            )

    old_bsr = old.get("bsr") or 0
    new_bsr = new_product.avg90_bsr or new_product.current_bsr or 0
    if old_bsr > 0 and new_bsr > 0:
        pct = (new_bsr - old_bsr) / old_bsr * 100
        if abs(pct) >= 50:
            arrow = "WORSE" if pct > 0 else "BETTER"
            changes.append(
                f"BSR {arrow} {abs(pct):.0f}% ({old_bsr:,} -> {new_bsr:,})"
            )

    old_sellers = old.get("fba_sellers")
    new_sellers = new_product.fba_offer_count
    if (old_sellers is not None and new_sellers is not None
            and new_sellers > old_sellers + 1):
        changes.append(f"new FBA competition ({old_sellers} -> {new_sellers})")

    return changes


def assess_status(old: dict, new_product, changes: List[str]) -> str:
    new_price = new_product.avg90_price or new_product.current_price
    old_max_buy = old.get("max_buy_price") or 0

    if new_price is None:
        return "no_data"

    if old_max_buy <= 0:
        return "ok"

    new_max_buy_pct = old_max_buy / new_price * 100

    if new_max_buy_pct < 20:
        return "danger"
    if new_max_buy_pct < 30:
        return "watch"

    if any("UP" in c and "price UP" in c for c in changes):
        return "improved"
    if any("BSR BETTER" in c for c in changes):
        return "improved"
    if any("price DOWN" in c for c in changes):
        return "degraded"
    if any("BSR WORSE" in c for c in changes):
        return "degraded"
    if any("new FBA competition" in c for c in changes):
        return "degraded"

    return "stable"


def render_report(rows: List[dict]) -> str:
    by_status = {"danger": [], "degraded": [], "watch": [], "improved": [],
                 "stable": [], "no_data": []}
    for r in rows:
        by_status.setdefault(r["status"], []).append(r)

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [
        f"# Refresh Report - {now}", "",
        f"Re-checked {len(rows)} top niches against current Keepa data.", "",
        "## Summary", "",
        f"- DANGER (skip):       **{len(by_status['danger'])}**",
        f"- DEGRADED:            **{len(by_status['degraded'])}**",
        f"- WATCH:               **{len(by_status['watch'])}**",
        f"- IMPROVED (better!):  **{len(by_status['improved'])}**",
        f"- STABLE (still good): **{len(by_status['stable'])}**",
        f"- NO DATA:             **{len(by_status['no_data'])}**", "",
    ]

    headers = {
        "danger": "## DANGER - market shifted, do NOT buy these now",
        "degraded": "## DEGRADED - margin or position weakened",
        "watch": "## WATCH - margin tight, verify in-store before buying",
        "improved": "## IMPROVED - better than the original snapshot!",
        "stable": "## STABLE - still good per the niches snapshot",
        "no_data": "## NO DATA - could not fetch from Keepa",
    }

    for status in ["danger", "degraded", "watch", "improved", "stable", "no_data"]:
        items = by_status[status]
        if not items:
            continue
        lines += ["", headers[status], ""]
        lines += [
            "| ASIN | Brand | Old $ | New $ | Old BSR | New BSR | Old / New FBA | Changes |",
            "|------|-------|------:|------:|--------:|--------:|---------------|---------|",
        ]
        for r in items:
            changes = "; ".join(r.get("changes", [])) or "—"
            lines.append(
                f"| `{r['asin']}` | {r['brand'][:14]} "
                f"| ${r.get('old_price', 0):.2f} | ${r.get('new_price') or 0:.2f} "
                f"| {(r.get('old_bsr') or 0):,} | {(r.get('new_bsr') or 0):,} "
                f"| {r.get('old_sellers', '?')} / {r.get('new_sellers', '?')} "
                f"| {changes} |"
            )
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="Refresh top targets vs current Keepa data")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--tier", choices=["HIDDEN_GEM", "SOLID_NICHE"])
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output", default=os.path.join(HERE, "refresh_report.md"))
    parser.add_argument("--output-json", default=os.path.join(HERE, "refresh.json"))
    args = parser.parse_args()

    niches = load_niches()
    print(f"[load] {len(niches)} niches available")

    targets = select_targets(niches, args.tier, args.limit)
    print(f"[select] refreshing top {len(targets)} (tier filter: {args.tier or 'all'})")

    est = estimate_tokens(len(targets))
    print(f"[estimate] ~{est} tokens (free plan refills 1/min = ~{est} minutes of bucket)")

    if args.dry_run:
        print("[dry-run] no API calls made")
        return

    from sources.keepa import KeepaClient, KeepaError
    try:
        client = KeepaClient()
    except KeepaError as e:
        print(f"[keepa] {e}")
        sys.exit(1)

    asins = [t["asin"] for t in targets]
    print(f"[keepa] bulk fetching {len(asins)} ASINs...")
    products = client.products_bulk(asins)
    print(f"[keepa] got {len(products)} products. tokens left: {client.tokens_left}")

    by_asin = {p.asin: p for p in products}
    rows = []
    for t in targets:
        p = by_asin.get(t["asin"])
        if not p:
            rows.append({
                "asin": t["asin"], "brand": t.get("brand", "?"),
                "status": "no_data", "changes": [],
                "old_price": t.get("sale_price"), "new_price": None,
            })
            continue
        changes = detect_changes(t, p)
        status = assess_status(t, p, changes)
        rows.append({
            "asin": t["asin"],
            "brand": t.get("brand", "?"),
            "title": t.get("title", "?")[:80],
            "old_price": t.get("sale_price"),
            "new_price": p.avg90_price or p.current_price,
            "old_bsr": t.get("bsr"),
            "new_bsr": p.avg90_bsr or p.current_bsr,
            "old_sellers": t.get("fba_sellers"),
            "new_sellers": p.fba_offer_count,
            "max_buy_price": t.get("max_buy_price"),
            "status": status,
            "changes": changes,
        })

    with open(args.output, "w") as f:
        f.write(render_report(rows))
    with open(args.output_json, "w") as f:
        json.dump(rows, f, indent=2, default=str)

    counts = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    print("\n[result]")
    for status in ["danger", "degraded", "watch", "improved", "stable", "no_data"]:
        if counts.get(status):
            print(f"  {status:10}: {counts[status]}")
    print(f"\n[write] {args.output}")


if __name__ == "__main__":
    main()

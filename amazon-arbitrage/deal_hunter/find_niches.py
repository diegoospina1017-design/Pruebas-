"""
Find Niches - re-rank sourcing targets by REAL opportunity, not just margin.

Best sellers are usually the wrong target: high competition, gated brands,
constant price wars. The real money is in the long tail — products with
decent demand AND low competition AND non-gated brands.

This script reads sourcing_*.json and re-scores every viable target on a
0-100 opportunity scale based on:

  - FBA seller count       (fewer = better)
  - BSR sweet spot         (1K - 100K = ideal; too high or too low penalized)
  - Margin headroom        (max_buy_pct between 30-50% sweet spot)
  - Brand gating risk      (known-gated brands penalized)
  - Buy Box stability      (low Amazon BB % preferred)
  - Return rate            (Low rate preferred)

Output: ranked report grouped by opportunity tier:
  - HIDDEN GEMS    (score 75+): low competition + good margin + non-gated
  - SOLID NICHES   (60-75):     decent on most factors
  - CROWDED MARGIN (40-60):     good margin but high competition or gated
  - SKIP           (<40):       not worth chasing

Usage:
    python3 find_niches.py
    python3 find_niches.py --min-score 60
    python3 find_niches.py --exclude-gated  # hard filter on likely-gated brands
"""

import argparse
import glob
import json
import os
import re
from typing import List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))


GATED_BRAND_PATTERNS = [
    r"\bnike\b", r"\badidas\b", r"\bunder\s*armour\b", r"\bdisney\b",
    r"\blego\b", r"\bfunko\b", r"\bpok[eé]mon\b", r"\bmattel\b", r"\bhasbro\b",
    r"\bapple\b", r"\bairpods\b", r"\bbeats\b", r"\bsamsung\b", r"\bsony\b",
    r"\bbose\b", r"\bxbox\b", r"\bplaystation\b", r"\bnintendo\b",
    r"\bhydro\s*flask\b", r"\bstanley\b", r"\byeti\b", r"\bowala\b",
    r"\bamazon\s*basics?\b", r"\bsolimo\b", r"\bpinzon\b",
    r"\bpampers\b", r"\bhuggies\b", r"\bcharmin\b", r"\bbounty\b", r"\bkleenex\b",
    r"\bcrest\b", r"\bcolgate\b", r"\boral[\s-]*b\b",
    r"\bcoach\b", r"\bmichael\s*kors\b", r"\bralph\s*lauren\b",
    r"\bdyson\b", r"\bkitchenaid\b", r"\binstant\s*pot\b", r"\bninja\b",
    r"\bkeurig\b", r"\bnespresso\b",
]

GATED_REGEX = re.compile("|".join(GATED_BRAND_PATTERNS), re.IGNORECASE)


def is_likely_gated(brand: str, title: str = "") -> bool:
    text = f"{brand} {title}".strip()
    return bool(GATED_REGEX.search(text))


def score_fba_sellers(n: Optional[int]) -> float:
    """Fewer is better. 1-2 sellers is ideal, >15 is brutal."""
    if n is None:
        return 12.0
    if n <= 1:
        return 25.0
    if n <= 3:
        return 22.0
    if n <= 5:
        return 17.0
    if n <= 10:
        return 10.0
    if n <= 15:
        return 5.0
    return 0.0


def score_bsr(bsr: Optional[int]) -> float:
    """Sweet spot is 1K-100K. Too low = too competitive. Too high = no demand."""
    if bsr is None or bsr <= 0:
        return 5.0
    if bsr < 100:
        return 8.0
    if bsr < 1000:
        return 14.0
    if bsr < 10_000:
        return 22.0
    if bsr < 50_000:
        return 25.0
    if bsr < 100_000:
        return 20.0
    if bsr < 250_000:
        return 12.0
    if bsr < 500_000:
        return 5.0
    return 0.0


def score_margin(max_buy_pct: float) -> float:
    """Sweet spot is 30-50%. Too low = thin. Too high = often suspicious or commodity."""
    if max_buy_pct < 20:
        return 5.0
    if max_buy_pct < 30:
        return 14.0
    if max_buy_pct < 40:
        return 22.0
    if max_buy_pct < 50:
        return 20.0
    if max_buy_pct < 60:
        return 16.0
    return 12.0


def score_bb_amazon(bb_pct: Optional[float]) -> float:
    """Lower Amazon buy-box share is better."""
    if bb_pct is None:
        return 8.0
    if bb_pct == 0:
        return 15.0
    if bb_pct <= 0.10:
        return 12.0
    if bb_pct <= 0.30:
        return 6.0
    return 0.0


def score_return_rate(rr: Optional[str]) -> float:
    if not rr:
        return 5.0
    s = rr.lower().strip()
    if s == "low":
        return 8.0
    if s == "medium":
        return 4.0
    return 0.0


def score_brand_gating(brand: str, title: str) -> float:
    if is_likely_gated(brand, title):
        return 0.0
    return 7.0


def opportunity_score(t: dict) -> dict:
    """Compute total opportunity score 0-100 with component breakdown."""
    components = {
        "fba_competition": score_fba_sellers(t.get("fba_sellers")),
        "bsr_demand": score_bsr(t.get("bsr")),
        "margin": score_margin(t.get("max_buy_pct") or 0),
        "amazon_bb": score_bb_amazon(t.get("bb_pct_amazon")),
        "returns": score_return_rate(t.get("return_rate")),
        "non_gated_brand": score_brand_gating(t.get("brand", ""), t.get("title", "")),
    }
    total = sum(components.values())
    return {"total": round(total, 1), "breakdown": components}


def tier(score: float) -> str:
    if score >= 75:
        return "HIDDEN_GEM"
    if score >= 60:
        return "SOLID_NICHE"
    if score >= 40:
        return "CROWDED"
    return "SKIP"


def load_all_targets() -> List[dict]:
    out = []
    for path in glob.glob(os.path.join(HERE, "sourcing_*.json")):
        try:
            with open(path) as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        src = os.path.basename(path).replace("sourcing_", "").replace("_keepa.json", "")
        for t in data:
            if t.get("status") in ("viable", "very_aggressive_target"):
                out.append({**t, "_cat": src})
    return out


def render(rows: List[dict]) -> str:
    by_tier = {"HIDDEN_GEM": [], "SOLID_NICHE": [], "CROWDED": [], "SKIP": []}
    for r in rows:
        by_tier[r["_tier"]].append(r)

    lines = [
        "# Niche Finder Report",
        "",
        "Re-ranks sourcing targets by REAL opportunity, not just margin.",
        "Score considers competition + BSR + margin + brand-gating + return rate.",
        "",
        "## Summary",
        "",
        f"- HIDDEN GEMS (score 75+):    **{len(by_tier['HIDDEN_GEM'])}** products",
        f"- SOLID NICHES (60-75):       **{len(by_tier['SOLID_NICHE'])}** products",
        f"- CROWDED but margin (40-60): **{len(by_tier['CROWDED'])}** products",
        f"- SKIP (<40):                 **{len(by_tier['SKIP'])}** products",
        "",
    ]

    tier_headers = {
        "HIDDEN_GEM": "## HIDDEN GEMS - chase these first",
        "SOLID_NICHE": "## SOLID NICHES - good secondary targets",
        "CROWDED": "## CROWDED - high margin but competition/gating risk",
        "SKIP": "## SKIP - not worth the effort",
    }

    for tier_name in ["HIDDEN_GEM", "SOLID_NICHE", "CROWDED", "SKIP"]:
        items = by_tier[tier_name]
        if not items:
            continue
        lines += ["", tier_headers[tier_name], ""]
        lines += [
            "| Score | ASIN | Brand | Product | Amazon $ | Max Buy | FBA | BSR | Gated? | Cat |",
            "|------:|------|-------|---------|---------:|--------:|----:|----:|--------|-----|",
        ]
        for r in items:
            gated = "YES" if is_likely_gated(r.get("brand", ""), r.get("title", "")) else "no"
            fbas = str(r.get("fba_sellers") if r.get("fba_sellers") is not None else "?")
            bsr = f"{r['bsr']:,}" if r.get("bsr") else "?"
            lines.append(
                f"| **{r['_score']:.0f}** | `{r['asin']}` | {r.get('brand', '?')[:12]} "
                f"| {r.get('title', '?')[:50]} | ${r.get('sale_price', 0):.2f} "
                f"| **${r['max_buy_price']:.2f}** | {fbas} | {bsr} | {gated} | {r['_cat'][:8]} |"
            )

    if by_tier["HIDDEN_GEM"]:
        lines += ["", "## Score breakdown for top hidden gems", ""]
        for r in by_tier["HIDDEN_GEM"][:5]:
            b = r["_breakdown"]
            lines += [
                f"### {r.get('brand', '?')} - {r.get('title', '?')[:60]}",
                f"- ASIN: `{r['asin']}`  |  Score: **{r['_score']:.0f}/100**",
                f"- FBA competition: {b['fba_competition']:.0f}/25  (fewer sellers = better)",
                f"- BSR demand: {b['bsr_demand']:.0f}/25  (sweet-spot demand = better)",
                f"- Margin: {b['margin']:.0f}/25",
                f"- Amazon BB share: {b['amazon_bb']:.0f}/15",
                f"- Return rate: {b['returns']:.0f}/8",
                f"- Non-gated brand: {b['non_gated_brand']:.0f}/7",
                "",
            ]

    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-score", type=float, default=0.0)
    parser.add_argument("--exclude-gated", action="store_true",
                        help="Hard filter out likely-gated brands")
    parser.add_argument("--output", default=os.path.join(HERE, "niches_report.md"))
    parser.add_argument("--output-json", default=os.path.join(HERE, "niches.json"))
    args = parser.parse_args()

    targets = load_all_targets()
    print(f"[load] {len(targets)} viable targets across all sourcing files")

    scored = []
    for t in targets:
        s = opportunity_score(t)
        t["_score"] = s["total"]
        t["_breakdown"] = s["breakdown"]
        t["_tier"] = tier(s["total"])
        if args.exclude_gated and is_likely_gated(t.get("brand", ""), t.get("title", "")):
            continue
        if t["_score"] < args.min_score:
            continue
        scored.append(t)

    scored.sort(key=lambda x: x["_score"], reverse=True)

    with open(args.output, "w", encoding="utf-8") as f:
        f.write(render(scored))
    with open(args.output_json, "w", encoding="utf-8") as f:
        json.dump(scored, f, indent=2)

    by_tier = {}
    for r in scored:
        by_tier[r["_tier"]] = by_tier.get(r["_tier"], 0) + 1

    print(f"[score] tier breakdown:")
    for t in ["HIDDEN_GEM", "SOLID_NICHE", "CROWDED", "SKIP"]:
        print(f"  {t:12} : {by_tier.get(t, 0):>3}")
    print(f"[write] {args.output}")


if __name__ == "__main__":
    main()

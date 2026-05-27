"""
Deal Hunter v1 - main entry point.

Usage:
    python3 hunter.py                       # fetch live Slickdeals + analyze
    python3 hunter.py --offline             # use sample_deals.json (no internet)
    python3 hunter.py --config myrules.json
    python3 hunter.py --asin-map mymap.json

Pipeline:
    1. Fetch raw deals (live RSS or sample)
    2. Apply filter rules from config.json
    3. Bridge to calculator using asin_map.json (your manual Amazon lookups)
    4. Generate ranked markdown report
"""

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from sources import slickdeals
from filters import filter_deals
from analyzer import analyze_all
from report import render


def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        return {k: v for k, v in data.items() if not k.startswith("_comment")}
    return data


def fetch_deals(offline: bool, sample_path: str) -> list:
    if offline:
        print(f"[mode] offline - loading {sample_path}")
        with open(sample_path, "r", encoding="utf-8") as f:
            return json.load(f)

    print("[mode] live - fetching Slickdeals feeds")
    deals = slickdeals.fetch_all()
    return [d.to_dict() for d in deals]


def main():
    parser = argparse.ArgumentParser(description="Amazon arbitrage deal hunter v1")
    parser.add_argument("--config", default=os.path.join(HERE, "config.json"))
    parser.add_argument("--asin-map", default=os.path.join(HERE, "asin_map.json"))
    parser.add_argument("--offline", action="store_true",
                        help="Use sample_deals.json instead of fetching live")
    parser.add_argument("--sample", default=os.path.join(HERE, "sources", "sample_deals.json"))
    parser.add_argument("--output-report", default=os.path.join(HERE, "report.md"))
    parser.add_argument("--output-candidates", default=os.path.join(HERE, "candidates.json"))
    args = parser.parse_args()

    config = load_json(args.config)
    asin_map = {}
    if os.path.exists(args.asin_map):
        asin_map = load_json(args.asin_map)
    else:
        print(f"[warn] no asin_map at {args.asin_map} - all deals will need manual lookup")

    raw_deals = fetch_deals(args.offline, args.sample)
    print(f"[fetch] {len(raw_deals)} raw deals")

    survivors = filter_deals(raw_deals, config)
    print(f"[filter] {len(survivors)} deals passed rules")

    analyzed = analyze_all(survivors, asin_map)
    analyzed_count = sum(1 for d in analyzed if d.get("_analysis", {}).get("status") == "analyzed")
    pending_count = len(analyzed) - analyzed_count
    print(f"[analyze] {analyzed_count} fully analyzed, {pending_count} pending Amazon lookup")

    top_n = config.get("output", {}).get("top_n", 15)
    report = render(analyzed, top_n=top_n)

    with open(args.output_report, "w", encoding="utf-8") as f:
        f.write(report)
    with open(args.output_candidates, "w", encoding="utf-8") as f:
        json.dump(analyzed, f, indent=2)

    print(f"[write] report -> {args.output_report}")
    print(f"[write] candidates JSON -> {args.output_candidates}")
    print()
    print("Next step: for deals in the 'Pending Amazon lookup' section,")
    print("  look them up on Amazon (or Keepa), add entries to asin_map.json,")
    print("  and re-run with --offline to re-analyze.")


if __name__ == "__main__":
    main()

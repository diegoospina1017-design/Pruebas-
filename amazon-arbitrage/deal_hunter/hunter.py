"""
Deal Hunter v1 - main entry point.

Usage:
    python3 hunter.py                       # live fetch + auto-Keepa if KEEPA_API_KEY set
    python3 hunter.py --offline             # use sample_deals.json (no internet)
    python3 hunter.py --no-keepa            # skip Keepa even if key is set
    python3 hunter.py --config myrules.json
    python3 hunter.py --asin-map mymap.json

Set KEEPA_API_KEY env var to enable auto-lookup:
    export KEEPA_API_KEY="your-key-from-keepa.com"

Pipeline:
    1. Fetch raw deals (live RSS or sample)
    2. Apply filter rules from config.json
    3. For each survivor: check asin_map.json first; if missing and Keepa is
       enabled, search Keepa, cache result back to asin_map.json
    4. Run profit calculator on each
    5. Generate ranked markdown report
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

try:
    from sources.keepa import KeepaClient, KeepaError
except ImportError as e:
    KeepaClient = None
    KeepaError = Exception


def load_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        return {k: v for k, v in data.items() if not k.startswith("_comment")}
    return data


def save_asin_map(path: str, asin_map: dict):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(asin_map, f, indent=2)


def fetch_deals(offline: bool, sample_path: str) -> list:
    if offline:
        print(f"[mode] offline - loading {sample_path}")
        with open(sample_path, "r", encoding="utf-8") as f:
            return json.load(f)

    print("[mode] live - fetching Slickdeals feeds")
    deals = slickdeals.fetch_all()
    return [d.to_dict() for d in deals]


def setup_keepa(disabled: bool) -> "KeepaClient | None":
    if disabled:
        print("[keepa] disabled via --no-keepa")
        return None
    if not os.environ.get("KEEPA_API_KEY"):
        print("[keepa] KEEPA_API_KEY not set - skipping auto-lookup")
        return None
    if KeepaClient is None:
        print("[keepa] client module failed to import - skipping")
        return None
    try:
        client = KeepaClient()
        print("[keepa] enabled - will auto-lookup deals missing from asin_map")
        return client
    except KeepaError as e:
        print(f"[keepa] init failed: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Amazon arbitrage deal hunter")
    parser.add_argument("--config", default=os.path.join(HERE, "config.json"))
    parser.add_argument("--asin-map", default=os.path.join(HERE, "asin_map.json"))
    parser.add_argument("--offline", action="store_true",
                        help="Use sample_deals.json instead of fetching live")
    parser.add_argument("--no-keepa", action="store_true",
                        help="Skip Keepa auto-lookup even if KEEPA_API_KEY is set")
    parser.add_argument("--sample", default=os.path.join(HERE, "sources", "sample_deals.json"))
    parser.add_argument("--output-report", default=os.path.join(HERE, "report.md"))
    parser.add_argument("--output-candidates", default=os.path.join(HERE, "candidates.json"))
    args = parser.parse_args()

    config = load_json(args.config)
    asin_map = {}
    if os.path.exists(args.asin_map):
        asin_map = load_json(args.asin_map)
    else:
        print(f"[warn] no asin_map at {args.asin_map} - starting fresh")

    keepa = setup_keepa(args.no_keepa)

    raw_deals = fetch_deals(args.offline, args.sample)
    print(f"[fetch] {len(raw_deals)} raw deals")

    survivors = filter_deals(raw_deals, config)
    print(f"[filter] {len(survivors)} deals passed rules")

    analyzed = analyze_all(survivors, asin_map, keepa=keepa)
    analyzed_count = sum(1 for d in analyzed if d.get("_analysis", {}).get("status") == "analyzed")
    pending_count = len(analyzed) - analyzed_count
    print(f"[analyze] {analyzed_count} fully analyzed, {pending_count} pending lookup")

    if keepa and keepa.tokens_left is not None:
        print(f"[keepa] tokens remaining: {keepa.tokens_left}")

    save_asin_map(args.asin_map, asin_map)
    print(f"[write] asin_map cached -> {args.asin_map}")

    top_n = config.get("output", {}).get("top_n", 15)
    report = render(analyzed, top_n=top_n)

    with open(args.output_report, "w", encoding="utf-8") as f:
        f.write(report)
    with open(args.output_candidates, "w", encoding="utf-8") as f:
        json.dump(analyzed, f, indent=2)

    print(f"[write] report -> {args.output_report}")
    print(f"[write] candidates -> {args.output_candidates}")


if __name__ == "__main__":
    main()

"""
Reporter agent - executive summary across all data sources.

Aggregates:
  - candidates.json     (today's hunter run output)
  - sourcing_*.json     (your viable sourcing targets)
  - inventory_tracker.csv (if you've started tracking purchases)
  - run.log             (today's hunter run log, optional)

Produces:
  - executive_summary.md (everything you need to know today, top-down)
  - Optionally posts summary to Telegram

Usage:
  python3 reporter.py                  # generate exec summary into the folder
  python3 reporter.py --telegram       # also push summary to your phone
  python3 reporter.py --top 10         # show top 10 of each section (default 5)
"""

import argparse
import csv
import glob
import json
import os
import sys
from collections import Counter
from datetime import datetime
from typing import List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from notifier import telegram_send


def load_json(path: str, default=None):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default


def load_all_targets() -> List[dict]:
    targets = []
    for path in glob.glob(os.path.join(HERE, "sourcing_*.json")):
        data = load_json(path, [])
        source = os.path.basename(path).replace("sourcing_", "").replace(".json", "")
        for t in data:
            if t.get("status") in ("viable", "very_aggressive_target"):
                t["_source"] = source
                targets.append(t)
    return targets


def load_tracker(path: str) -> List[dict]:
    if not os.path.exists(path):
        return []
    rows = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                if r.get("sku") and r["sku"].strip() and not r["sku"].startswith("EX"):
                    rows.append(r)
    except OSError:
        pass
    return rows


def section_hot_buys(candidates: List[dict], top: int) -> List[str]:
    hot = [d for d in candidates if d.get("_target_match", {}).get("is_hot_buy")]
    hot.sort(key=lambda d: d["_target_match"]["margin_vs_max"], reverse=True)
    if not hot:
        return ["## HOT BUYS today", "", "_None today. Hunter found no Slickdeals deals "
                "matching a sourcing target at or below max buy price._", ""]

    lines = ["## HOT BUYS today - act on these", "",
             f"Found **{len(hot)}** hot buy(s). Listed by biggest margin first.", ""]
    lines += ["| # | Retailer | Deal $ | Max Buy | Margin | Brand / ASIN | Deal link |",
              "|---|----------|-------:|--------:|-------:|--------------|-----------|"]
    for i, d in enumerate(hot[:top], 1):
        m = d["_target_match"]
        lines.append(
            f"| {i} | {d.get('retailer') or '?'} | **${d['deal_price']:.2f}** "
            f"| ${m['target_max_buy']:.2f} | +${m['margin_vs_max']:.2f} "
            f"| {m.get('target_brand', '?')} / `{m['target_asin']}` "
            f"| [link]({d['url']}) |"
        )
    lines.append("")
    return lines


def section_target_watch(candidates: List[dict], top: int) -> List[str]:
    near = [d for d in candidates
            if d.get("_target_match") and not d["_target_match"].get("is_hot_buy")]
    near.sort(key=lambda d: d["_target_match"]["margin_vs_max"], reverse=True)
    if not near:
        return []

    lines = ["## Watching - target matches above your max buy", "",
             f"{len(near)} deal(s) matched a target but still priced above your max buy. "
             "Worth monitoring in case the price drops.", ""]
    lines += ["| # | Brand | Retailer | Deal $ | Max Buy | Over by | Link |",
              "|---|-------|----------|-------:|--------:|--------:|------|"]
    for i, d in enumerate(near[:top], 1):
        m = d["_target_match"]
        lines.append(
            f"| {i} | {m.get('target_brand', '?')} | {d.get('retailer') or '?'} "
            f"| ${d['deal_price']:.2f} | ${m['target_max_buy']:.2f} "
            f"| ${-m['margin_vs_max']:.2f} | [link]({d['url']}) |"
        )
    lines.append("")
    return lines


def section_target_inventory(targets: List[dict], top: int) -> List[str]:
    if not targets:
        return ["## Sourcing inventory",
                "_No sourcing targets loaded. Export best sellers from Keepa and run "
                "sourcing_from_excel.py first._", ""]

    by_source = Counter(t["_source"] for t in targets)
    lines = [f"## Sourcing inventory ({len(targets)} viable targets across "
             f"{len(by_source)} categories)", ""]
    for src, n in sorted(by_source.items(), key=lambda kv: kv[1], reverse=True):
        lines.append(f"- **{src.replace('_keepa', '').replace('_', ' ').title()}**: {n} targets")
    lines.append("")

    sorted_targets = sorted(
        [t for t in targets if t.get("max_buy_price", 0) > 0 and t.get("sale_price")],
        key=lambda t: t.get("max_buy_pct", 0),
        reverse=True,
    )

    lines += [f"### Top {top} targets by max-buy-% (best margin headroom)", "",
              "| # | ASIN | Brand | Product | Amazon $ | Max Buy | % | Cat |",
              "|---|------|-------|---------|---------:|--------:|--:|-----|"]
    for i, t in enumerate(sorted_targets[:top], 1):
        lines.append(
            f"| {i} | `{t['asin']}` | {t.get('brand', '?')[:12]} "
            f"| {t.get('title', '?')[:50]} | ${t['sale_price']:.2f} "
            f"| **${t['max_buy_price']:.2f}** | {t.get('max_buy_pct', 0):.0f}% "
            f"| {t.get('category', '?')[:20]} |"
        )
    lines.append("")
    return lines


def section_tracker(rows: List[dict]) -> List[str]:
    if not rows:
        return ["## Inventory tracker", "",
                "_No real purchases tracked yet. Once you make your first FBA purchase, "
                "add it to `tracker/inventory_tracker.csv` and this section will summarize._",
                ""]

    total_cost = 0.0
    total_profit = 0.0
    sold_count = 0
    active_count = 0
    skus_active = []
    for r in rows:
        try:
            cost = float(r.get("total_cost") or 0)
            total_cost += cost
        except ValueError:
            pass
        try:
            profit = float(r.get("actual_profit") or 0)
            total_profit += profit
        except ValueError:
            pass
        status = (r.get("status") or "").lower()
        if status in ("sold_out", "completed"):
            sold_count += 1
        else:
            active_count += 1
            skus_active.append(r.get("sku"))

    lines = ["## Inventory tracker", "",
             f"- Active SKUs: **{active_count}**",
             f"- Sold-out SKUs: **{sold_count}**",
             f"- Total invested (lifetime): **${total_cost:,.2f}**",
             f"- Total profit (lifetime): **${total_profit:,.2f}**",
             ""]
    if active_count > 0:
        lines.append(f"Active SKUs: {', '.join(skus_active[:10])}"
                     + (f" (+{active_count-10} more)" if active_count > 10 else ""))
        lines.append("")
    return lines


def section_recommendations(hot_buy_count: int, watch_count: int,
                            targets: List[dict], tracker: List[dict]) -> List[str]:
    lines = ["## What to do today", ""]
    actions = []

    if hot_buy_count > 0:
        actions.append(f"**BUY**: Act on the {hot_buy_count} HOT BUY(S) above - "
                       "scan with Amazon Seller App first, then purchase if not gated.")
    if watch_count > 0:
        actions.append(f"**WATCH**: {watch_count} deals near your max buy - "
                       "check again tomorrow in case price drops.")
    if not targets:
        actions.append("**EXPORT**: No sourcing targets loaded. Export a category's "
                       "best sellers from Keepa, then run sourcing_from_excel.py.")
    elif len(targets) < 50:
        actions.append(f"**EXPAND**: Only {len(targets)} targets loaded. "
                       "Add more categories (Office Products, Arts & Crafts, Kitchen) for more matches.")
    if not tracker:
        actions.append("**TRACK**: No inventory tracked. Once you make your first "
                       "purchase, add a row to `tracker/inventory_tracker.csv`.")
    if not actions:
        actions.append("Nothing urgent. Run the hunter again tomorrow morning.")

    for i, a in enumerate(actions, 1):
        lines.append(f"{i}. {a}")
    lines.append("")
    return lines


def build_report(candidates: List[dict], targets: List[dict], tracker: List[dict],
                 top: int) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    hot = [d for d in candidates if d.get("_target_match", {}).get("is_hot_buy")]
    near = [d for d in candidates
            if d.get("_target_match") and not d["_target_match"].get("is_hot_buy")]

    lines = [f"# Executive Summary - {now}", "",
             "_Generated by the reporter agent. Reads hunter output, sourcing lists, "
             "and inventory tracker._", "",
             "## At a glance", "",
             f"- HOT BUYS today: **{len(hot)}**",
             f"- Target matches watching: **{len(near)}**",
             f"- Total deals analyzed: **{len(candidates)}**",
             f"- Viable sourcing targets in library: **{len(targets)}**",
             f"- Active inventory SKUs: **{sum(1 for r in tracker if (r.get('status') or '').lower() not in ('sold_out', 'completed'))}**",
             ""]

    lines += section_hot_buys(candidates, top)
    lines += section_target_watch(candidates, top)
    lines += section_recommendations(len(hot), len(near), targets, tracker)
    lines += section_target_inventory(targets, top)
    lines += section_tracker(tracker)

    return "\n".join(lines) + "\n"


def telegram_summary(candidates: List[dict], targets: List[dict], tracker: List[dict]) -> str:
    hot = [d for d in candidates if d.get("_target_match", {}).get("is_hot_buy")]
    near = [d for d in candidates
            if d.get("_target_match") and not d["_target_match"].get("is_hot_buy")]
    active = sum(1 for r in tracker if (r.get("status") or "").lower() not in ("sold_out", "completed"))

    lines = [
        f"*Daily Deal Hunter Summary*",
        f"_{datetime.now().strftime('%Y-%m-%d %H:%M')}_",
        "",
        f"HOT BUYS: *{len(hot)}*",
        f"Watching: {len(near)}",
        f"Sourcing targets: {len(targets)}",
        f"Active SKUs: {active}",
    ]
    if hot:
        lines.append("")
        lines.append("*Top hot buys:*")
        for d in hot[:3]:
            m = d["_target_match"]
            lines.append(f"- {m.get('target_brand', '?')} @ ${d['deal_price']:.2f} "
                         f"({d.get('retailer') or '?'}) margin ${m['margin_vs_max']:.2f}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Aggregate hunter + sourcing + tracker into exec summary")
    parser.add_argument("--candidates", default=os.path.join(HERE, "candidates.json"))
    parser.add_argument("--tracker", default=os.path.join(HERE, "..", "tracker", "inventory_tracker.csv"))
    parser.add_argument("--output", default=os.path.join(HERE, "executive_summary.md"))
    parser.add_argument("--top", type=int, default=5)
    parser.add_argument("--telegram", action="store_true", help="Also send summary to Telegram")
    args = parser.parse_args()

    candidates = load_json(args.candidates, [])
    targets = load_all_targets()
    tracker = load_tracker(args.tracker)

    print(f"[load] {len(candidates)} candidates, {len(targets)} targets, {len(tracker)} tracked SKUs")

    report = build_report(candidates, targets, tracker, args.top)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"[write] {args.output}")

    if args.telegram:
        token = os.environ.get("TELEGRAM_BOT_TOKEN")
        chat_id = os.environ.get("TELEGRAM_CHAT_ID")
        if not (token and chat_id):
            print("[telegram] not configured - skip")
        else:
            text = telegram_summary(candidates, targets, tracker)
            ok = telegram_send(token, chat_id, text)
            print(f"[telegram] {'sent' if ok else 'failed'}")


if __name__ == "__main__":
    main()

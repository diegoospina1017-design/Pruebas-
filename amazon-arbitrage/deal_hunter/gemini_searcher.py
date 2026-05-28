"""
Gemini Searcher - same job as claude_searcher.py but using Google Gemini API.

Why Gemini for this use case:
  - Free tier available (~15 requests/min for gemini-2.5-flash)
  - Google Search grounding is native (uses real Google results)
  - Cheaper per call than Claude for single-shot search workflows

Modes (same as claude_searcher):
  --mock              Cost-free preview - no API call
  --show-prompt       Print prompt + cost estimate
  (default)           Real call. Requires GEMINI_API_KEY env var.

Setup:
  1. Get free API key at https://aistudio.google.com/apikey
  2. export GEMINI_API_KEY="..."
  3. pip3 install google-genai
  4. python3 gemini_searcher.py --mock --from-niches --limit 5  (test)
  5. python3 gemini_searcher.py --from-niches --limit 5         (real)

Cost (gemini-2.5-flash + Google Search grounding):
  - Model: ~$0.075/M input, $0.30/M output (very cheap)
  - Google Search grounding: ~$0.035 per grounded prompt
  - Total: ~$0.04 per run regardless of target count
  - Free tier covers basic usage for testing
"""

import argparse
import glob
import json
import os
import random
import re
import sys
from datetime import datetime
from typing import List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


SYSTEM_PROMPT = """You are an expert retail arbitrage scout for an Amazon FBA reseller \
based in Christiansburg, Virginia. Your job is to find current online deals on specific \
Amazon best-seller products the user wants to source for resale.

# How the user makes money

The user buys products at a discount from retailers (Walmart, Target, Kohls, etc.) \
and resells them on Amazon FBA. They have already calculated the maximum price they \
can pay for each product to hit 30% ROI and at least $3 net profit, accounting for \
Amazon fees, FBA fulfillment, inbound shipping, and storage. That number is "Max Buy".

# What you must do

For each product in the target list, use Google Search to find the current best price \
across major US online retailers. Be efficient - one good search per product is enough \
if it surfaces what you need.

# Sources to prefer (in order)

1. Walmart.com (look for "rollback" pricing and prices ending in odd cents like .89)
2. Target.com (clearance section, RedCard discounts)
3. Kohls.com (coupons + Kohls Cash stack)
4. TJMaxx.com / Marshalls.com / HomeGoods.com (clearance)
5. BestBuy.com (open box, clearance)
6. Costco.com, Sams.com (bulk pricing)
7. HomeDepot.com, Lowes.com (tools, garden)

Avoid: AliExpress, Temu, Wish, eBay individual sellers, Facebook Marketplace.

# Strict rules

1. Only return deals where price <= Max Buy. Skip products that exceed Max Buy.
2. Verify brand and pack size match. A 6-pack at the source must match a 6-pack on Amazon.
3. Never fabricate prices. If Google Search didn't find a real listing, skip that product.
4. US shipping required (user is in Virginia). Skip pickup-only deals from chains >30 miles away.
5. Note stock status - skip clearly out-of-stock listings.

# Output format

Return ONLY a valid JSON array, with no markdown fences, no commentary before or after. \
Use this exact schema:

[
  {
    "asin": "string - ASIN from target list",
    "title": "string - actual product title from the deal page",
    "retailer": "string - Walmart, Target, Kohls, BestBuy, HomeDepot, Lowes, TJ Maxx, Marshalls, HomeGoods, Costco, Macys",
    "deal_price": number,
    "list_price": number_or_null,
    "url": "string - direct product URL, not a search results page",
    "in_stock": boolean,
    "confidence": "high|medium|low",
    "notes": "string - clearance, coupon stack, YMMV, limit per customer, etc."
  }
]

If you find no deals at or below any Max Buy, return [].
"""


def load_targets(min_max_buy_pct: float = 25.0, limit: int = 25) -> List[dict]:
    all_targets = []
    for path in glob.glob(os.path.join(HERE, "sourcing_*.json")):
        try:
            with open(path) as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            continue
        source = os.path.basename(path).replace("sourcing_", "").replace(".json", "")
        for t in data:
            if t.get("status") not in ("viable", "very_aggressive_target"):
                continue
            if (t.get("max_buy_pct") or 0) < min_max_buy_pct:
                continue
            all_targets.append({**t, "_source": source})
    all_targets.sort(key=lambda x: x.get("max_buy_pct", 0), reverse=True)
    return all_targets[:limit]


def load_from_niches(min_score: float = 60.0, limit: int = 25,
                     exclude_gated: bool = True) -> List[dict]:
    path = os.path.join(HERE, "niches.json")
    if not os.path.exists(path):
        print(f"[error] {path} not found - run `python3 find_niches.py` first")
        sys.exit(1)
    with open(path) as f:
        data = json.load(f)
    try:
        from find_niches import is_likely_gated
    except ImportError:
        is_likely_gated = lambda b, t="": False
    out = []
    for t in data:
        if t.get("_score", 0) < min_score:
            continue
        if exclude_gated and is_likely_gated(t.get("brand", ""), t.get("title", "")):
            continue
        out.append({**t, "_source": "niches"})
    out.sort(key=lambda x: x.get("_score", 0), reverse=True)
    return out[:limit]


def build_user_prompt(targets: List[dict]) -> str:
    lines = [
        "Search Google for current deals on these specific Amazon best-seller products.",
        "Find deals AT or BELOW the 'Max Buy' price. Return JSON array only.",
        "",
        "## Target products",
        "",
    ]
    for i, t in enumerate(targets, 1):
        lines.append(f"{i}. ASIN `{t['asin']}` | **{t.get('brand', '?')}**")
        lines.append(f"   Title: {t.get('title', '?')[:100]}")
        lines.append(
            f"   Amazon: ${t['sale_price']:.2f}  |  MAX BUY: **${t['max_buy_price']:.2f}**  "
            f"|  Category: {t.get('category', '?')}"
        )
        lines.append("")
    lines.append("Return the JSON array only. No code fences, no commentary.")
    return "\n".join(lines)


def estimate_cost(targets: List[dict]) -> dict:
    """gemini-2.5-flash + Google Search grounding."""
    system_tokens = 950
    user_tokens = 150 + len(targets) * 75
    output_tokens = 150 + len(targets) * 55

    input_cost_per_m = 0.075
    output_cost_per_m = 0.30
    grounding_per_prompt = 0.035

    per_run = (
        (system_tokens + user_tokens) / 1_000_000 * input_cost_per_m
        + output_tokens / 1_000_000 * output_cost_per_m
        + grounding_per_prompt
    )
    return {
        "system_tokens": system_tokens,
        "user_tokens": user_tokens,
        "output_tokens": output_tokens,
        "per_run_usd": round(per_run, 4),
        "monthly_30_runs_usd": round(per_run * 30, 2),
    }


def mock_search(targets: List[dict]) -> List[dict]:
    random.seed(42)
    retailers = ["Walmart", "Target", "Kohls", "BestBuy", "TJ Maxx", "Marshalls"]
    notes_pool = [
        "Clearance pricing - red sticker in-store",
        "Limit 2 per customer",
        "YMMV - check your local store",
        "Free shipping on $35+ orders",
        "Online exclusive deal",
        "Stack with Kohls Cash for extra savings",
        "RedCard 5% off applies",
    ]
    n_to_match = max(2, int(len(targets) * 0.4))
    matched = random.sample(targets, min(n_to_match, len(targets)))
    deals = []
    for t in matched:
        max_buy = t["max_buy_price"]
        sale = t["sale_price"]
        if random.random() < 0.65:
            deal_price = round(random.uniform(max_buy * 0.55, max_buy * 0.95), 2)
        else:
            deal_price = round(random.uniform(max_buy * 1.10, max_buy * 1.40), 2)
        retailer = random.choice(retailers)
        deals.append({
            "asin": t["asin"],
            "title": t.get("title", "?")[:100],
            "retailer": retailer,
            "deal_price": deal_price,
            "list_price": round(sale * 1.10, 2) if random.random() > 0.4 else None,
            "url": f"https://www.{retailer.lower().replace(' ', '')}.com/ip/{t['asin']}",
            "in_stock": random.random() > 0.15,
            "confidence": random.choice(["high", "high", "medium"]),
            "notes": random.choice(notes_pool),
        })
    return deals


def call_gemini_real(targets: List[dict], verbose: bool = False) -> List[dict]:
    """Real Gemini API call with Google Search grounding."""
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        print("ERROR: google-genai package not installed.")
        print("  Install with: pip3 install google-genai")
        sys.exit(1)

    if not os.environ.get("GEMINI_API_KEY"):
        print("ERROR: GEMINI_API_KEY environment variable not set.")
        print("  1. Get a free API key at https://aistudio.google.com/apikey")
        print("  2. export GEMINI_API_KEY=\"...\"")
        print("  Or use --mock to preview the flow without an API key.")
        sys.exit(1)

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    user_prompt = build_user_prompt(targets)

    print("[gemini] calling gemini-2.5-flash with Google Search grounding...")
    print("[gemini] this takes ~30-60 seconds while Google searches each product")

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=0.3,
            ),
        )
    except Exception as e:
        print(f"[gemini] API call failed: {e}")
        sys.exit(1)

    usage = getattr(response, "usage_metadata", None)
    if usage:
        print(
            f"[gemini] usage: prompt={getattr(usage, 'prompt_token_count', '?')}  "
            f"candidates={getattr(usage, 'candidates_token_count', '?')}  "
            f"total={getattr(usage, 'total_token_count', '?')}"
        )

    text = response.text or ""

    if verbose:
        print("\n[gemini] full response:")
        print("-" * 70)
        print(text)
        print("-" * 70)

    grounding_chunks = []
    try:
        cand = response.candidates[0] if response.candidates else None
        if cand and cand.grounding_metadata and cand.grounding_metadata.grounding_chunks:
            grounding_chunks = cand.grounding_metadata.grounding_chunks
            print(f"[gemini] grounded with {len(grounding_chunks)} search result(s)")
    except (AttributeError, IndexError):
        pass

    match = re.search(r"\[\s*(?:\{.*?\}\s*,?\s*)*\]", text, re.DOTALL)
    if not match:
        print("[gemini] no JSON array detected in response")
        print("[gemini] first 800 chars:")
        print(text[:800])
        return []

    try:
        deals = json.loads(match.group(0))
    except json.JSONDecodeError as e:
        print(f"[gemini] JSON parse failed: {e}")
        print(f"[gemini] attempted: {match.group(0)[:400]}")
        return []

    return deals


def convert_to_hunter_format(deals: List[dict]) -> List[dict]:
    out = []
    for d in deals:
        deal_price = d.get("deal_price")
        list_price = d.get("list_price")
        disc = None
        if deal_price and list_price and list_price > deal_price:
            disc = (list_price - deal_price) / list_price * 100
        out.append({
            "source": "gemini_search",
            "feed": "google",
            "title": d.get("title", ""),
            "deal_price": deal_price,
            "list_price": list_price,
            "discount_pct": disc,
            "retailer": d.get("retailer"),
            "url": d.get("url") or f"gemini://no-url/{d.get('asin', '?')}",
            "description": f"[Gemini {d.get('confidence', '?')} conf] {d.get('notes', '')}",
            "posted_at": datetime.utcnow().isoformat() + "Z",
            "_gemini_asin": d.get("asin"),
            "_gemini_in_stock": d.get("in_stock", True),
            "_gemini_confidence": d.get("confidence"),
        })
    return out


def render_pretty_report(deals: List[dict], targets: List[dict], mode: str) -> str:
    target_by_asin = {t["asin"]: t for t in targets}
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    hot_buys, near_miss = [], []
    not_found_asins = set(t["asin"] for t in targets)

    for d in deals:
        asin = d.get("asin")
        not_found_asins.discard(asin)
        target = target_by_asin.get(asin)
        if not target:
            continue
        max_buy = target.get("max_buy_price", 0)
        deal_price = d.get("deal_price", 0)
        entry = {**d, "_target": target, "_max_buy": max_buy}
        if deal_price <= max_buy and deal_price > 0:
            entry["_savings"] = max_buy - deal_price
            hot_buys.append(entry)
        else:
            entry["_over"] = (deal_price or 0) - max_buy
            near_miss.append(entry)

    hot_buys.sort(key=lambda x: x.get("_savings", 0), reverse=True)
    near_miss.sort(key=lambda x: x.get("_over", 999))
    not_found = [target_by_asin[a] for a in not_found_asins if a in target_by_asin]
    not_found.sort(key=lambda t: t.get("_score", 0), reverse=True)

    mode_label = "MOCK (no API call)" if mode == "mock" else "LIVE Gemini search"
    lines = [
        f"# Gemini Search Report",
        f"_{now}  |  Mode: {mode_label}_",
        "",
        "## At a glance",
        "",
        f"- HOT BUYS (price <= your max buy): **{len(hot_buys)}**",
        f"- Near-miss (above max buy): **{len(near_miss)}**",
        f"- No deal found yet: **{len(not_found)}**",
        f"- Total targets searched: **{len(targets)}**",
        "",
    ]

    if hot_buys:
        lines += [
            "## HOT BUYS - act on these",
            "",
            "These are at or below your Max Buy price. Scan ASIN in Amazon Seller "
            "App before buying to confirm you can sell the brand.",
            "",
        ]
        for i, d in enumerate(hot_buys, 1):
            t = d["_target"]
            stock = "IN STOCK" if d.get("_gemini_in_stock", True) else "low stock"
            lines += [
                f"### {i}. {t.get('brand', '?')} - {d.get('title', t.get('title', ''))[:80]}",
                "",
                f"- **Deal: ${d['deal_price']:.2f}** at **{d.get('retailer', '?')}** ({stock})",
                f"- Your max buy: ${d['_max_buy']:.2f}  ->  margin **+${d['_savings']:.2f} below max**",
                f"- Amazon sells at ${t.get('sale_price', 0):.2f}  |  BSR {t.get('bsr') or '?'}  |  FBA sellers: {t.get('fba_sellers') or '?'}",
                f"- Opportunity score: {t.get('_score', '?')}/100  |  Tier: {t.get('_tier', '?')}",
                f"- ASIN: `{t['asin']}`  |  Confidence: {d.get('confidence', '?')}",
            ]
            if d.get("notes"):
                lines.append(f"- {d['notes']}")
            lines += [f"- Buy link: {d.get('url', '?')}", ""]

    if near_miss:
        lines += [
            "## Near-miss - too expensive today, watch for price drops",
            "",
            "| ASIN | Brand | Title | Retailer | Deal $ | Max Buy | Over by |",
            "|------|-------|-------|----------|-------:|--------:|--------:|",
        ]
        for d in near_miss:
            t = d["_target"]
            lines.append(
                f"| `{t['asin']}` | {t.get('brand', '?')[:14]} | {(d.get('title') or t.get('title', ''))[:50]} "
                f"| {d.get('retailer', '?')} | ${d.get('deal_price', 0):.2f} | ${d['_max_buy']:.2f} "
                f"| ${d['_over']:.2f} |"
            )
        lines.append("")

    if not_found:
        lines += [
            "## No deal found yet",
            "",
            "Gemini did not find a current deal at or below max buy for these. "
            "Worth checking physical stores (TJ Maxx, Marshalls, Ross clearance "
            "often beats online).",
            "",
            "| ASIN | Brand | Title | Amazon $ | Max Buy | BSR | Score |",
            "|------|-------|-------|---------:|--------:|----:|------:|",
        ]
        for t in not_found[:20]:
            lines.append(
                f"| `{t['asin']}` | {t.get('brand', '?')[:14]} | {t.get('title', '')[:50]} "
                f"| ${t.get('sale_price', 0):.2f} | ${t.get('max_buy_price', 0):.2f} "
                f"| {(t.get('bsr') or 0):,} | {t.get('_score', '?')} |"
            )
        lines.append("")

    lines += ["## Next steps", ""]
    if hot_buys:
        lines.append(f"1. **Verify the {len(hot_buys)} HOT BUY(S)** with the Amazon Seller App")
        lines.append("2. Buy the ones not gated for your account")
        lines.append("3. Track each purchase in `tracker/inventory_tracker.csv`")
    else:
        lines.append("1. No actionable hot buys today - try `--limit 20` to expand search")
        lines.append("2. Or check physical stores for the 'no deal found' items")
    lines.append("")

    return "\n".join(lines) + "\n"


def print_cost(targets: List[dict]) -> None:
    cost = estimate_cost(targets)
    print("=" * 72)
    print("ESTIMATED COST PER RUN (Gemini 2.5 Flash + Google Search grounding)")
    print("=" * 72)
    print(f"  Per run:                ${cost['per_run_usd']:.4f}")
    print(f"  ~30 runs/month:          ${cost['monthly_30_runs_usd']:.2f}")
    print()
    print(f"  System tokens:    ~{cost['system_tokens']:,}")
    print(f"  User tokens:      ~{cost['user_tokens']:,}")
    print(f"  Output tokens:    ~{cost['output_tokens']:,}")
    print(f"  Google grounding: ~$0.035 per run (or free under free tier daily quota)")
    print("=" * 72)
    print()


def print_deals_table(deals: List[dict], targets: List[dict]) -> None:
    target_max = {t["asin"]: t["max_buy_price"] for t in targets}
    print()
    print("=" * 90)
    print(f"DEALS FOUND ({len(deals)})")
    print("=" * 90)
    if not deals:
        print("  (none)")
        return
    hot, miss = [], []
    for d in deals:
        max_buy = target_max.get(d.get("asin"))
        if max_buy is not None and d.get("deal_price") is not None and d["deal_price"] <= max_buy:
            hot.append((d, max_buy))
        else:
            miss.append((d, max_buy))
    if hot:
        print("\n[HOT BUYS - at or below Max Buy]")
        for d, mb in hot:
            margin = mb - d["deal_price"] if mb else 0
            print(
                f"  ${d['deal_price']:>7.2f} (max ${mb:.2f}, +${margin:.2f}) "
                f"{d.get('retailer', '?'):12} {d.get('title', '?')[:50]}"
            )
    if miss:
        print("\n[Near-miss / above Max Buy]")
        for d, mb in miss:
            over = (d["deal_price"] - mb) if mb else 0
            print(
                f"  ${d['deal_price']:>7.2f} (max ${mb:.2f}, -${over:.2f}) "
                f"{d.get('retailer', '?'):12} {d.get('title', '?')[:50]}"
            )
    print()


def main():
    parser = argparse.ArgumentParser(description="Gemini-powered deal searcher")
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--show-prompt", action="store_true")
    parser.add_argument("--from-niches", action="store_true",
                        help="Load from niches.json instead of sourcing_*.json")
    parser.add_argument("--min-score", type=float, default=60.0)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--min-pct", type=float, default=30.0)
    parser.add_argument("--include-gated", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--output", default=os.path.join(HERE, "gemini_deals.json"))
    parser.add_argument("--report", default=os.path.join(HERE, "gemini_report.md"))
    args = parser.parse_args()

    if args.from_niches:
        targets = load_from_niches(
            min_score=args.min_score, limit=args.limit,
            exclude_gated=not args.include_gated,
        )
        print(f"[load] {len(targets)} niches (score >= {args.min_score}, gated excluded: {not args.include_gated})")
    else:
        targets = load_targets(min_max_buy_pct=args.min_pct, limit=args.limit)
        print(f"[load] {len(targets)} targets (max_buy_pct >= {args.min_pct}%)")

    if not targets:
        print("[load] no targets found")
        sys.exit(1)

    if args.show_prompt:
        print("\n" + "=" * 72)
        print("SYSTEM PROMPT")
        print("=" * 72)
        print(SYSTEM_PROMPT[:600] + f"\n... [{len(SYSTEM_PROMPT)} chars total]")
        print("\n" + "=" * 72)
        print("USER PROMPT")
        print("=" * 72)
        print(build_user_prompt(targets)[:1500] + "\n... [truncated]")
        print()
        print_cost(targets)
        return

    print_cost(targets)

    if args.mock:
        print("[MOCK MODE] no API call - generating plausible deals for demo")
        deals = mock_search(targets)
    else:
        deals = call_gemini_real(targets, verbose=args.verbose)

    print_deals_table(deals, targets)

    hunter_format = convert_to_hunter_format(deals)
    with open(args.output, "w") as f:
        json.dump(hunter_format, f, indent=2)
    print(f"[write] {args.output}")

    mode = "mock" if args.mock else "live"
    with open(args.report, "w") as f:
        f.write(render_pretty_report(deals, targets, mode))
    print(f"[write] {args.report}")
    print(f"\n[next] open the report: open {args.report}")


if __name__ == "__main__":
    main()

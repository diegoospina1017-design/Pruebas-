"""
Claude Searcher - autonomous web search agent for arbitrage deal discovery.

Modes:
  --mock              Cost-free preview: shows the prompt, generates plausible
                      mock deals, and feeds them into the existing pipeline.
                      No API call, no ANTHROPIC_API_KEY needed.
  --show-prompt       Print the exact prompt and estimated cost without calling.
  (default)           Real call to Claude API with the web_search tool.
                      Requires ANTHROPIC_API_KEY in env.

What it does (real mode):
  1. Loads top N viable sourcing targets from sourcing_*.json
  2. Builds a prompt with each ASIN + brand + Amazon price + Max Buy
  3. Calls claude-opus-4-7 with the web_search tool enabled
  4. Claude autonomously searches Walmart, Target, Kohls, etc. for current prices
  5. Returns structured JSON of deals at or below your Max Buy price
  6. Writes claude_deals.json in the format the existing hunter expects

Prompt caching: the system prompt + workflow rules are cached on the first run.
Repeat runs the same day pay ~0.1x the input cost for the cached portion.
(Caching activates only when the cached prefix is >= 4096 tokens.)
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
Amazon best-seller products the user is sourcing.

# How the user makes money

The user buys products at a discount from a retailer (Walmart, Target, Kohls, etc.) \
and resells them on Amazon FBA. They have already pre-calculated the maximum price \
they can pay for each product to hit a 30% ROI and at least $3 net profit, accounting \
for Amazon fees, FBA fulfillment cost, inbound shipping from Virginia, and storage. \
That price is the "Max Buy" you'll see in the target list.

# What you must do

For each product in the target list, search the web for current prices. Use the \
`web_search` tool aggressively. Try multiple queries per product if needed:
- Exact product name + brand
- Brand + clearance / sale / price drop
- ASIN-based searches (sometimes work for major retailers)

When you find a candidate, verify the match by checking:
- Brand and model match exactly (not just similar)
- Pack size matches (a 6-pack at the source must equal a 6-pack on the Amazon listing)
- Color/size variant matches if relevant

# Sources to prefer

US online retailers that ship to Virginia, in rough order of arbitrage value:
- Walmart.com (best clearance signal: "rollback", final price below $X.XX with odd ending)
- Target.com (RedCard 5% off available, look for clearance section)
- Kohls.com (stack Kohls Cash + coupons)
- BestBuy.com (open box and clearance)
- HomeDepot.com / Lowes.com (tools, home & garden)
- TJMaxx.com / Marshalls.com / HomeGoods.com (deep clearance)
- Macys.com (frequent 60-70% off events)

Avoid: AliExpress, Temu, Wish, eBay private sellers, Facebook Marketplace.

# Rules - DO NOT VIOLATE

1. Only return deals where the price is at or below the listed Max Buy price.
   If the cheapest price you find is above Max Buy, do NOT include that product.
   Returning a deal above Max Buy is worse than returning nothing.

2. Verify product match. If you are not 95% confident the deal is the SAME product as \
   the ASIN, skip it. A close match in the wrong size/pack is a returns disaster on FBA.

3. Never fabricate prices. If a search did not surface a real listing, skip the product.

4. Check stock status. If the listing shows "Out of stock" or "Limited stock", note it.

5. US shipping required. The user is in Virginia. Skip international-only or pickup-only \
   deals from stores not within 30 miles of Christiansburg, VA (24073). Major chains \
   with online ordering and US shipping are fine.

# Output format

Return a JSON array of deals. Use this EXACT schema:

```json
[
  {
    "asin": "string - the ASIN from the target list",
    "title": "string - product title as shown on the deal page",
    "retailer": "string - one of: Walmart, Target, Kohls, BestBuy, HomeDepot, Lowes, TJ Maxx, Marshalls, HomeGoods, Macys",
    "deal_price": number - the current price in USD,
    "list_price": number or null - the strikethrough/MSRP price if shown,
    "url": "string - direct product URL (not a search results page)",
    "in_stock": boolean,
    "confidence": "string - one of: high, medium, low - how sure are you this is the right product",
    "notes": "string - relevant context: clearance, coupon stack, YMMV, in-store only, limit per customer, etc."
  }
]
```

If you find zero deals at or below Max Buy, return `[]`.

Provide the JSON array as your final output. Before the JSON, you may include a brief \
summary of what you searched and what you found. The JSON must be the LAST thing in \
your response, in a code block."""


def load_targets(min_max_buy_pct: float = 25.0, limit: int = 25) -> List[dict]:
    """Load top viable sourcing targets across all sourcing_*.json files."""
    all_targets = []
    for path in glob.glob(os.path.join(HERE, "sourcing_*.json")):
        try:
            with open(path, "r", encoding="utf-8") as f:
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


def build_user_prompt(targets: List[dict]) -> str:
    lines = [
        "Search the web for current deals on these specific Amazon best-seller products.",
        "Find deals AT or BELOW the 'Max Buy' price for each. Use web_search aggressively.",
        "",
        "## Target products",
        "",
    ]
    for i, t in enumerate(targets, 1):
        lines.append(
            f"{i}. ASIN `{t['asin']}` | **{t.get('brand', '?')}**"
        )
        lines.append(
            f"   Title: {t.get('title', '?')[:100]}"
        )
        lines.append(
            f"   Amazon price: ${t['sale_price']:.2f}  |  "
            f"MAX BUY: **${t['max_buy_price']:.2f}**  |  "
            f"Category: {t.get('category', '?')}"
        )
        lines.append("")
    lines.append(
        "Return the JSON array of deals you found per the schema in your instructions. "
        "Skip any product where no deal at or below Max Buy exists. Be thorough."
    )
    return "\n".join(lines)


def estimate_cost(targets: List[dict], avg_searches_per_target: float = 1.5) -> dict:
    """Rough cost estimate for claude-opus-4-7."""
    system_tokens = 1100
    user_tokens = 200 + len(targets) * 80
    output_tokens = 200 + len(targets) * 60
    searches = max(3, int(len(targets) * avg_searches_per_target))

    input_cost_per_m = 5.00
    output_cost_per_m = 25.00
    cache_write_mult = 1.25
    cache_read_mult = 0.10
    web_search_cost_per_1k = 10.00

    first_run = (
        (system_tokens * cache_write_mult + user_tokens) / 1_000_000 * input_cost_per_m
        + output_tokens / 1_000_000 * output_cost_per_m
        + searches * web_search_cost_per_1k / 1000
    )
    cached_run = (
        (system_tokens * cache_read_mult + user_tokens) / 1_000_000 * input_cost_per_m
        + output_tokens / 1_000_000 * output_cost_per_m
        + searches * web_search_cost_per_1k / 1000
    )
    return {
        "system_tokens": system_tokens,
        "user_tokens": user_tokens,
        "output_tokens": output_tokens,
        "searches": searches,
        "first_run_usd": round(first_run, 4),
        "cached_run_usd": round(cached_run, 4),
        "monthly_30_runs_usd": round(first_run + 29 * cached_run, 2),
    }


def mock_search(targets: List[dict]) -> List[dict]:
    """No API call. Generates plausible deals to demonstrate the pipeline shape."""
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
        "Open box - still factory sealed",
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
            "confidence": random.choice(["high", "high", "high", "medium"]),
            "notes": random.choice(notes_pool),
        })
    return deals


def call_claude_real(targets: List[dict], verbose: bool = False) -> List[dict]:
    """Real Claude API call with web_search tool. Requires ANTHROPIC_API_KEY."""
    try:
        import anthropic
    except ImportError:
        print("ERROR: anthropic package not installed.")
        print("  Install with: pip3 install anthropic")
        sys.exit(1)

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY environment variable not set.")
        print("  1. Get a key at https://console.anthropic.com")
        print("  2. Add credit ($5-10 to start)")
        print("  3. export ANTHROPIC_API_KEY=\"sk-ant-...\"")
        print("  Or use --mock to preview the flow without an API key.")
        sys.exit(1)

    client = anthropic.Anthropic()
    user_prompt = build_user_prompt(targets)

    print("[claude] calling claude-opus-4-7 with web_search and adaptive thinking...")
    print("[claude] this will take ~30-90 seconds while Claude searches the web")

    response = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=16000,
        thinking={"type": "adaptive"},
        cache_control={"type": "ephemeral"},
        system=[
            {"type": "text", "text": SYSTEM_PROMPT},
        ],
        messages=[
            {"role": "user", "content": user_prompt},
        ],
        tools=[
            {"type": "web_search_20260209", "name": "web_search"},
        ],
    )

    usage = response.usage
    print(f"[claude] stop_reason: {response.stop_reason}")
    print(
        f"[claude] usage: input={usage.input_tokens}  "
        f"output={usage.output_tokens}  "
        f"cache_read={usage.cache_read_input_tokens}  "
        f"cache_write={usage.cache_creation_input_tokens}"
    )

    text_blocks = [b.text for b in response.content if b.type == "text"]
    if not text_blocks:
        print("[claude] no text in response - check the message structure")
        if verbose:
            for b in response.content:
                print(f"  block.type = {b.type}")
        return []

    full_text = "\n\n".join(text_blocks)

    if verbose:
        print("\n[claude] full text response:")
        print("-" * 70)
        print(full_text)
        print("-" * 70)

    match = re.search(r"\[\s*(?:\{.*?\}\s*,?\s*)*\]", full_text, re.DOTALL)
    if not match:
        print("[claude] no JSON array detected in response")
        print("[claude] first 800 chars of response:")
        print(full_text[:800])
        return []

    try:
        deals = json.loads(match.group(0))
    except json.JSONDecodeError as e:
        print(f"[claude] JSON parse failed: {e}")
        print(f"[claude] attempted to parse: {match.group(0)[:400]}")
        return []

    return deals


def convert_to_hunter_format(deals: List[dict]) -> List[dict]:
    """Convert Claude's deal output into the shape the existing hunter expects."""
    out = []
    for d in deals:
        deal_price = d.get("deal_price")
        list_price = d.get("list_price")
        disc = None
        if deal_price and list_price and list_price > deal_price:
            disc = (list_price - deal_price) / list_price * 100

        url = d.get("url", "")
        title = d.get("title", "")
        out.append({
            "source": "claude_search",
            "feed": "web",
            "title": title,
            "deal_price": deal_price,
            "list_price": list_price,
            "discount_pct": disc,
            "retailer": d.get("retailer"),
            "url": url or f"claude://no-url/{d.get('asin', '?')}",
            "description": (
                f"[Claude {d.get('confidence', '?')} conf] {d.get('notes', '')}"
            ),
            "posted_at": datetime.utcnow().isoformat() + "Z",
            "_claude_asin": d.get("asin"),
            "_claude_in_stock": d.get("in_stock", True),
            "_claude_confidence": d.get("confidence"),
        })
    return out


def print_prompt_preview(targets: List[dict]) -> None:
    print()
    print("=" * 72)
    print("SYSTEM PROMPT (cached - same every run)")
    print("=" * 72)
    print(SYSTEM_PROMPT[:600] + f"\n... [truncated, {len(SYSTEM_PROMPT)} chars total]")
    print()
    print("=" * 72)
    print("USER PROMPT (varies per run)")
    print("=" * 72)
    print(build_user_prompt(targets)[:1500] + "\n... [truncated]")
    print()


def print_cost(targets: List[dict]) -> None:
    cost = estimate_cost(targets)
    print("=" * 72)
    print("ESTIMATED COST PER RUN")
    print("=" * 72)
    print(f"  First run today (cache miss):  ${cost['first_run_usd']:.4f}")
    print(f"  Subsequent today (cache hit):  ${cost['cached_run_usd']:.4f}")
    print(f"  ~30 runs/month estimate:        ${cost['monthly_30_runs_usd']:.2f}")
    print()
    print(f"  System tokens:        ~{cost['system_tokens']:,} (cached)")
    print(f"  User tokens:          ~{cost['user_tokens']:,} (varies)")
    print(f"  Output tokens:        ~{cost['output_tokens']:,}")
    print(f"  Web searches:         ~{cost['searches']} @ $0.01 each")
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

    hot = []
    miss = []
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
    parser = argparse.ArgumentParser(description="Claude-powered deal searcher")
    parser.add_argument("--mock", action="store_true",
                        help="Cost-free demo: no API call, fake deals")
    parser.add_argument("--show-prompt", action="store_true",
                        help="Print prompt + cost estimate and exit (no API call)")
    parser.add_argument("--limit", type=int, default=10,
                        help="Max targets to search (default 10)")
    parser.add_argument("--min-pct", type=float, default=30.0,
                        help="Min max_buy_pct filter (default 30)")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--output", default=os.path.join(HERE, "claude_deals.json"))
    args = parser.parse_args()

    targets = load_targets(min_max_buy_pct=args.min_pct, limit=args.limit)
    print(f"[load] {len(targets)} targets selected (max_buy_pct >= {args.min_pct}%)")

    if not targets:
        print("[load] no viable targets - run sourcing_from_excel.py first")
        sys.exit(1)

    if args.show_prompt:
        print_prompt_preview(targets)
        print_cost(targets)
        print("Use --mock to see the output shape without spending tokens.")
        return

    print_cost(targets)

    if args.mock:
        print("[MOCK MODE] no API call - generating plausible deals for demo")
        deals = mock_search(targets)
    else:
        deals = call_claude_real(targets, verbose=args.verbose)

    print_deals_table(deals, targets)

    hunter_format = convert_to_hunter_format(deals)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(hunter_format, f, indent=2)
    print(f"[write] {args.output}")
    print(
        f"[next] feed into hunter: deals are in hunter format and can be cross-checked "
        f"against your 82 sourcing targets via target_matcher"
    )


if __name__ == "__main__":
    main()

"""
Cross-check Slickdeals deals against the sourcing target lists.

Loads all sourcing_*.json files (viable targets from your Keepa exports)
and tries to match each Slickdeals deal against them. When a deal matches
a known target AND the deal price <= target max_buy_price, it's a HOT BUY.
"""

import glob
import json
import os
import re
import unicodedata
from typing import List, Optional, Tuple


def _ascii_fold(s: str) -> str:
    """Strip accents/diacritics so Pokémon -> Pokemon."""
    if not s:
        return ""
    nfd = unicodedata.normalize("NFD", s)
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn")

STOPWORDS = {
    "the", "a", "an", "and", "or", "for", "with", "of", "in", "on", "at",
    "to", "by", "from", "as", "is", "it", "this", "that", "pack", "set",
    "new", "free", "shipping", "store", "pickup", "on", "off", "save",
    "case", "rolls", "count", "ct", "oz", "lb", "lbs", "fl", "size", "pcs",
    "pieces", "piece", "pc", "x", "and",
}


def _tokenize(text: str) -> set:
    if not text:
        return set()
    folded = _ascii_fold(text).lower()
    tokens = re.findall(r"\b[a-z0-9]{2,}\b", folded)
    return {t for t in tokens if t not in STOPWORDS}


def _normalize_brand(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", _ascii_fold(s or "").lower())


def load_targets(sourcing_dir: str) -> List[dict]:
    """Load all viable products from sourcing_*.json files in a directory."""
    targets = []
    pattern = os.path.join(sourcing_dir, "sourcing_*.json")
    for path in glob.glob(pattern):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"  [targets] failed to load {os.path.basename(path)}: {e}")
            continue

        source_file = os.path.basename(path).replace("sourcing_", "").replace(".json", "")
        for t in data:
            if t.get("status") not in ("viable", "very_aggressive_target"):
                continue
            if not t.get("max_buy_price") or not t.get("sale_price"):
                continue
            t = {**t, "_source_file": source_file}
            t["_tokens"] = _tokenize(t.get("title", ""))
            t["_brand_norm"] = _normalize_brand(t.get("brand", ""))
            targets.append(t)
    return targets


def match_deal_to_target(deal: dict, targets: List[dict]) -> Optional[dict]:
    """Find best-matching target for a Slickdeals deal. Returns None if no confident match."""
    deal_title = deal.get("title", "") or ""
    deal_tokens = _tokenize(deal_title)
    if not deal_tokens:
        return None
    deal_title_lower = _ascii_fold(deal_title).lower()

    best_match = None
    best_score = 0.0

    for t in targets:
        score = 0.0

        brand = t["_brand_norm"]
        if brand and len(brand) >= 3:
            normalized_deal = re.sub(r"[^a-z0-9]", "", deal_title_lower)
            if brand in normalized_deal:
                score += 45

        target_tokens = t["_tokens"]
        if target_tokens:
            overlap = len(deal_tokens & target_tokens)
            jaccard = overlap / len(deal_tokens | target_tokens)
            recall = overlap / len(target_tokens)
            score += (jaccard * 30) + (recall * 25)

        if score > best_score:
            best_score = score
            best_match = t

    if best_score < 55 or best_match is None:
        return None

    deal_price = deal.get("deal_price") or 0
    max_buy = best_match.get("max_buy_price", 0)
    margin_vs_max = round(max_buy - deal_price, 2)

    return {
        "match_score": round(best_score, 1),
        "target_asin": best_match["asin"],
        "target_brand": best_match.get("brand"),
        "target_title": best_match.get("title", "")[:80],
        "target_category": best_match.get("category"),
        "target_amazon_price": best_match.get("sale_price"),
        "target_max_buy": max_buy,
        "target_bsr": best_match.get("bsr"),
        "target_fba_sellers": best_match.get("fba_sellers"),
        "target_source": best_match["_source_file"],
        "deal_price": deal_price,
        "margin_vs_max": margin_vs_max,
        "is_hot_buy": deal_price > 0 and deal_price <= max_buy,
    }


def attach_target_matches(deals: List[dict], targets: List[dict]) -> List[dict]:
    """Annotate each deal with _target_match if found. Mutates deals in place."""
    for d in deals:
        match = match_deal_to_target(d, targets)
        if match:
            d["_target_match"] = match
    return deals


if __name__ == "__main__":
    import sys
    HERE = os.path.dirname(os.path.abspath(__file__))
    targets = load_targets(HERE)
    print(f"Loaded {len(targets)} viable targets across all sourcing files")
    by_source = {}
    for t in targets:
        by_source.setdefault(t["_source_file"], 0)
        by_source[t["_source_file"]] += 1
    for src, n in sorted(by_source.items()):
        print(f"  {src}: {n} targets")

    if len(sys.argv) > 1:
        test_title = " ".join(sys.argv[1:])
        fake_deal = {"title": test_title, "deal_price": 0}
        result = match_deal_to_target(fake_deal, targets)
        print(f"\nTest match for: {test_title!r}")
        if result:
            print(json.dumps(result, indent=2))
        else:
            print("  no confident match found")

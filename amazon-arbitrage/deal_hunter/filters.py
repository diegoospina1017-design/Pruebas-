"""
Rule engine for filtering deals against user config.
"""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class FilterResult:
    passed: bool
    score: float
    reasons: List[str]


def _contains_any(text: str, terms: List[str]) -> Optional[str]:
    text_lower = text.lower()
    for term in terms:
        if term.lower() in text_lower:
            return term
    return None


def evaluate(deal: dict, config: dict) -> FilterResult:
    reasons = []
    title = deal.get("title", "") or ""
    desc = deal.get("description", "") or ""
    combined = f"{title} {desc}"

    deal_price = deal.get("deal_price")
    if deal_price is None:
        return FilterResult(False, 0.0, ["no price extracted"])

    price_cfg = config.get("price", {})
    min_p = price_cfg.get("min_deal_price", 0)
    max_p = price_cfg.get("max_deal_price", 10_000)
    if deal_price < min_p:
        return FilterResult(False, 0.0, [f"price ${deal_price} below min ${min_p}"])
    if deal_price > max_p:
        return FilterResult(False, 0.0, [f"price ${deal_price} above max ${max_p}"])

    disc_cfg = config.get("discount", {})
    min_disc = disc_cfg.get("min_discount_pct", 0)
    discount_pct = deal.get("discount_pct")
    if discount_pct is None:
        reasons.append("discount% unknown (no list price)")
    elif discount_pct < min_disc:
        return FilterResult(False, 0.0, [f"discount {discount_pct:.0f}% below min {min_disc}%"])

    retailer_cfg = config.get("retailers", {})
    include_only = retailer_cfg.get("include_only", [])
    excluded = retailer_cfg.get("exclude", [])
    retailer = deal.get("retailer")

    if include_only:
        if not retailer:
            return FilterResult(False, 0.0, ["retailer unknown but include_only is set"])
        if not any(r.lower() == retailer.lower() for r in include_only):
            return FilterResult(False, 0.0, [f"retailer {retailer} not in include_only"])

    if retailer and any(r.lower() == retailer.lower() for r in excluded):
        return FilterResult(False, 0.0, [f"retailer {retailer} in exclude list"])

    kw_cfg = config.get("keywords", {})
    hit = _contains_any(title, kw_cfg.get("exclude_in_title", []))
    if hit:
        return FilterResult(False, 0.0, [f"title contains excluded keyword '{hit}'"])

    hit = _contains_any(combined, kw_cfg.get("exclude_gated_brands", []))
    if hit:
        return FilterResult(False, 0.0, [f"likely gated brand '{hit}'"])

    hit = _contains_any(combined, kw_cfg.get("exclude_categories", []))
    if hit:
        return FilterResult(False, 0.0, [f"excluded category indicator '{hit}'"])

    size_cfg = config.get("size_hints", {})
    hit = _contains_any(title, size_cfg.get("exclude_in_title", []))
    if hit:
        return FilterResult(False, 0.0, [f"likely oversize ('{hit}')"])

    score = 0.0
    if discount_pct is not None:
        score += discount_pct
    if 10 <= deal_price <= 30:
        score += 15
    elif 5 <= deal_price < 10 or 30 < deal_price <= 50:
        score += 8

    if deal.get("feed") == "popular":
        score += 10

    return FilterResult(True, score, reasons or ["passed all checks"])


def filter_deals(deals: List[dict], config: dict) -> List[dict]:
    """Return surviving deals sorted by score desc, each with `_filter` field attached."""
    results = []
    for d in deals:
        r = evaluate(d, config)
        if r.passed:
            d = {**d, "_score": r.score, "_filter_notes": r.reasons}
            results.append(d)
    results.sort(key=lambda x: x["_score"], reverse=True)
    return results

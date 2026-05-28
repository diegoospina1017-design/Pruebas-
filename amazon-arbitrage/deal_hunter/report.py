"""
Generate a Markdown report from analyzed deals.
"""

from datetime import datetime
from typing import List


def _profit_icon(rec: str) -> str:
    if rec.startswith("STRONG BUY"):
        return "**STRONG BUY**"
    if rec.startswith("BUY"):
        return "**BUY**"
    if rec.startswith("MARGINAL"):
        return "_marginal_"
    return "skip"


def render(deals: List[dict], top_n: int = 15) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    analyzed = [d for d in deals if d.get("_analysis", {}).get("status") == "analyzed"]
    pending = [d for d in deals if d.get("_analysis", {}).get("status") == "needs_amazon_lookup"]

    analyzed.sort(key=lambda d: d["_analysis"]["net_profit"], reverse=True)
    pending.sort(key=lambda d: d.get("_score", 0), reverse=True)

    lines = [
        f"# Deal Hunter Report",
        f"_Generated {now}_",
        "",
        f"- Total candidates after filtering: **{len(deals)}**",
        f"- Fully analyzed (with Amazon data): **{len(analyzed)}**",
        f"- Pending Amazon lookup: **{len(pending)}**",
        "",
    ]

    if analyzed:
        lines.append("## Fully analyzed (ranked by net profit)")
        lines.append("")
        lines.append("| # | Title | Retailer | Cost | Amazon | Net profit | ROI | Rec |")
        lines.append("|---|-------|----------|------|--------|-----------|-----|-----|")
        for i, d in enumerate(analyzed[:top_n], 1):
            a = d["_analysis"]
            lines.append(
                f"| {i} | {d['title'][:50]} "
                f"| {d.get('retailer') or '?'} "
                f"| ${d['deal_price']:.2f} "
                f"| ${a['amazon_sale_price']:.2f} "
                f"| ${a['net_profit']:.2f} "
                f"| {a['roi_pct']:.0f}% "
                f"| {_profit_icon(a['recommendation'])} |"
            )
        lines.append("")

        lines.append("### Details for top candidates")
        for i, d in enumerate(analyzed[:5], 1):
            a = d["_analysis"]
            source = a.get("data_source", "manual")
            score_str = f" (Keepa match {a['match_score']:.0f}/100)" if a.get("match_score") else ""
            lines.extend([
                f"\n#### {i}. {d['title']}",
                f"- Deal: ${d['deal_price']:.2f} at {d.get('retailer') or '?'} ({d.get('discount_pct', 0):.0f}% off)",
                f"- Amazon ASIN: `{a.get('asin')}` selling at ${a['amazon_sale_price']:.2f}  _[source: {source}{score_str}]_",
            ])
            if a.get("keepa_title"):
                lines.append(f"- Keepa matched title: _{a['keepa_title'][:120]}_")
            lines.extend([
                f"- Net profit per unit: **${a['net_profit']:.2f}** (ROI {a['roi_pct']:.0f}%, margin {a['margin_pct']:.1f}%)",
                f"- Recommendation: **{a['recommendation']}**",
                f"- Fees: referral ${a['fee_breakdown']['referral']:.2f}, "
                f"FBA ${a['fee_breakdown']['fba_fulfillment']:.2f}, "
                f"storage ${a['fee_breakdown']['storage']:.2f}, "
                f"inbound ${a['fee_breakdown']['inbound_shipping']:.2f}",
            ])
            if a.get("warnings"):
                lines.append(f"- Warnings: {'; '.join(a['warnings'])}")
            if a.get("alternatives"):
                lines.append(f"- Other Keepa candidates (if match seems wrong):")
                for alt in a["alternatives"][:3]:
                    price_str = f"${alt['price']:.2f}" if alt.get("price") else "?"
                    lines.append(f"    - `{alt['asin']}` ({price_str}, score {alt['score']:.0f}): {alt['title']}")
            lines.append(f"- Deal link: {d['url']}")

    if pending:
        lines.append("")
        lines.append("## Pending Amazon lookup")
        lines.append("")
        lines.append("These deals passed filtering but need Amazon-side data before analysis. "
                     "Add entries to `asin_map.json` and re-run.")
        lines.append("")
        lines.append("| # | Score | Title | Retailer | Deal $ | Discount | URL |")
        lines.append("|---|------:|-------|----------|-------:|---------:|-----|")
        for i, d in enumerate(pending[:top_n], 1):
            disc = d.get("discount_pct")
            disc_str = f"{disc:.0f}%" if disc is not None else "?"
            lines.append(
                f"| {i} "
                f"| {d.get('_score', 0):.0f} "
                f"| {d['title'][:50]} "
                f"| {d.get('retailer') or '?'} "
                f"| ${d['deal_price']:.2f} "
                f"| {disc_str} "
                f"| {d['url']} |"
            )

    return "\n".join(lines) + "\n"

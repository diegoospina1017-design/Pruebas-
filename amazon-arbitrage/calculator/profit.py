"""
Profit calculator for Amazon FBA retail/online arbitrage.

Usage:
    python profit.py
    or import: from profit import calculate
"""

from dataclasses import dataclass
from typing import Optional

from fees import fba_fulfillment_fee, monthly_storage_fee, referral_fee
from shipping import avg_inbound_shipping, supplies_cost_per_unit


@dataclass
class ProductInput:
    name: str
    cost_per_unit: float
    sale_price: float
    weight_lb: float
    length_in: float
    width_in: float
    height_in: float
    category: str = "default"
    size_tier: str = "standard"
    units_per_box: int = 1
    sales_tax_pct: float = 0.0
    months_in_storage: float = 1.0
    peak_season: bool = False
    use_partnered_carrier: bool = True


@dataclass
class ProfitBreakdown:
    name: str
    revenue: float
    cogs: float
    sales_tax: float
    inbound_shipping: float
    supplies: float
    referral_fee: float
    fba_fee: float
    storage_fee: float
    total_costs: float
    net_profit: float
    margin_pct: float
    roi_pct: float
    recommendation: str

    def pretty(self) -> str:
        lines = [
            f"\n  === {self.name} ===",
            f"  Revenue (Amazon sells for):        ${self.revenue:>8.2f}",
            f"  -- COSTS --",
            f"  Cost of goods (you pay):           ${self.cogs:>8.2f}",
            f"  Sales tax on purchase:             ${self.sales_tax:>8.2f}",
            f"  Inbound shipping (VA -> FBA):      ${self.inbound_shipping:>8.2f}",
            f"  Prep supplies (box/bag/label):     ${self.supplies:>8.2f}",
            f"  Amazon referral fee:               ${self.referral_fee:>8.2f}",
            f"  FBA fulfillment fee:               ${self.fba_fee:>8.2f}",
            f"  Storage fee (est.):                ${self.storage_fee:>8.2f}",
            f"  Total costs:                       ${self.total_costs:>8.2f}",
            f"  -- RESULT --",
            f"  Net profit per unit:               ${self.net_profit:>8.2f}",
            f"  Margin:                            {self.margin_pct:>8.1f}%",
            f"  ROI:                               {self.roi_pct:>8.1f}%",
            f"  Recommendation:                    {self.recommendation}",
        ]
        return "\n".join(lines)


def calculate(p: ProductInput) -> ProfitBreakdown:
    revenue = p.sale_price
    cogs = p.cost_per_unit
    sales_tax = cogs * p.sales_tax_pct

    inbound = avg_inbound_shipping(
        p.weight_lb, p.units_per_box, p.use_partnered_carrier
    )
    supplies = supplies_cost_per_unit(p.units_per_box)
    ref_fee = referral_fee(p.sale_price, p.category)
    fba_fee = fba_fulfillment_fee(p.weight_lb, p.size_tier)
    storage = monthly_storage_fee(
        p.length_in, p.width_in, p.height_in,
        p.size_tier, p.months_in_storage, p.peak_season,
    )

    total_costs = cogs + sales_tax + inbound + supplies + ref_fee + fba_fee + storage
    net_profit = revenue - total_costs
    margin_pct = (net_profit / revenue * 100) if revenue > 0 else 0
    total_investment = cogs + sales_tax + inbound + supplies
    roi_pct = (net_profit / total_investment * 100) if total_investment > 0 else 0

    if net_profit >= 3 and roi_pct >= 30:
        rec = "BUY - meets minimum criteria"
    elif net_profit >= 5 and roi_pct >= 50:
        rec = "STRONG BUY"
    elif net_profit > 0 and roi_pct >= 20:
        rec = "MARGINAL - only if BSR is excellent"
    else:
        rec = "SKIP - margin too thin"

    return ProfitBreakdown(
        name=p.name,
        revenue=revenue,
        cogs=cogs,
        sales_tax=sales_tax,
        inbound_shipping=inbound,
        supplies=supplies,
        referral_fee=ref_fee,
        fba_fee=fba_fee,
        storage_fee=storage,
        total_costs=total_costs,
        net_profit=net_profit,
        margin_pct=margin_pct,
        roi_pct=roi_pct,
        recommendation=rec,
    )


def interactive():
    print("\n=== Amazon FBA Profit Calculator (from Christiansburg, VA) ===\n")
    name = input("Product name: ").strip() or "Unnamed"
    cost = float(input("Your cost per unit ($): "))
    sale = float(input("Amazon sale price ($): "))
    weight = float(input("Weight per unit (lb): "))
    length = float(input("Length (inches): "))
    width = float(input("Width (inches): "))
    height = float(input("Height (inches): "))

    print("\nCategories: default, beauty, beauty_under_10, consumer_electronics,")
    print("  clothing, toys_games, kitchen, home_garden, grocery, pet_supplies,")
    print("  health_personal_care, sports, tools_home_improvement, books, ...")
    category = input("Category [default]: ").strip() or "default"

    print("\nSize tiers: small_standard (<=1 lb, <=15x12x0.75 in), standard, large_bulky")
    size = input("Size tier [standard]: ").strip() or "standard"

    tax_input = input("Sales tax on your purchase % [0]: ").strip()
    tax = float(tax_input) / 100 if tax_input else 0.0

    months_input = input("Expected months in FBA storage [1]: ").strip()
    months = float(months_input) if months_input else 1.0

    peak_input = input("Will it sit in storage during Oct-Dec? [y/N]: ").strip().lower()
    peak = peak_input == "y"

    product = ProductInput(
        name=name, cost_per_unit=cost, sale_price=sale,
        weight_lb=weight, length_in=length, width_in=width, height_in=height,
        category=category, size_tier=size, sales_tax_pct=tax,
        months_in_storage=months, peak_season=peak,
    )

    result = calculate(product)
    print(result.pretty())
    print()


if __name__ == "__main__":
    print("\n--- Example 1: kitchen gadget from Walmart clearance ---")
    example = ProductInput(
        name="Silicone spatula set (clearance)",
        cost_per_unit=4.50,
        sale_price=18.99,
        weight_lb=0.6,
        length_in=12, width_in=3, height_in=2,
        category="kitchen",
        size_tier="standard",
        sales_tax_pct=0.053,
        months_in_storage=1.5,
    )
    print(calculate(example).pretty())

    print("\n--- Example 2: same spatula but shipped 24 per box ---")
    example2 = ProductInput(
        name="Silicone spatula set (24 per box)",
        cost_per_unit=4.50,
        sale_price=18.99,
        weight_lb=0.6,
        length_in=12, width_in=3, height_in=2,
        category="kitchen",
        size_tier="standard",
        sales_tax_pct=0.053,
        months_in_storage=1.5,
        units_per_box=24,
    )
    print(calculate(example2).pretty())

    print("\n--- Example 3: high-margin toy, bulk shipped, peak season ---")
    example3 = ProductInput(
        name="Plush toy (12 per box, Q4 peak)",
        cost_per_unit=6.00,
        sale_price=22.99,
        weight_lb=0.4,
        length_in=8, width_in=6, height_in=4,
        category="toys_games",
        size_tier="standard",
        sales_tax_pct=0.053,
        months_in_storage=2.0,
        peak_season=True,
        units_per_box=12,
    )
    print(calculate(example3).pretty())

    print("\n--- Run interactively? [y/N]: ", end="")
    if input().strip().lower() == "y":
        interactive()

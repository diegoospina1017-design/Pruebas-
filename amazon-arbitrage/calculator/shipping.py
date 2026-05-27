"""
Inbound shipping cost estimator from Christiansburg, VA (ZIP 24073) to Amazon FBA warehouses.

Rates based on:
- UPS Ground / Amazon Partnered Carrier (SPD) retail estimates 2024
- Christiansburg sits in UPS Zone 2-5 to most East Coast FBA hubs
- Amazon Partnered Carrier typically gives ~30-40% discount vs UPS retail

Common FBA destinations from VA and their zones from 24073:
  CLT* (Charlotte, NC)   - Zone 2
  GSP* (Spartanburg, SC) - Zone 3
  ATL* (Atlanta, GA)     - Zone 4
  BWI* (Baltimore, MD)   - Zone 3
  PHL* (Philadelphia)    - Zone 4
  EWR* (NJ)              - Zone 4
  IND* (Indianapolis)    - Zone 4
  ORD* (Chicago)         - Zone 5
  DFW* (Dallas)          - Zone 6
  LAX/ONT* (California)  - Zone 8
"""

UPS_GROUND_ZONE_RATES = {
    2: {"base": 9.50, "per_lb": 0.55},
    3: {"base": 10.20, "per_lb": 0.75},
    4: {"base": 11.40, "per_lb": 1.05},
    5: {"base": 13.10, "per_lb": 1.45},
    6: {"base": 15.30, "per_lb": 1.85},
    7: {"base": 17.80, "per_lb": 2.30},
    8: {"base": 20.50, "per_lb": 2.75},
}

PARTNERED_CARRIER_DISCOUNT = 0.35

DESTINATION_PROBABILITY = {
    2: 0.15,
    3: 0.25,
    4: 0.30,
    5: 0.15,
    6: 0.08,
    7: 0.04,
    8: 0.03,
}


def ups_ground_cost(weight_lb: float, zone: int) -> float:
    """Retail UPS Ground rate from 24073 to a given zone."""
    if zone not in UPS_GROUND_ZONE_RATES:
        zone = 5
    billable_weight = max(1.0, weight_lb)
    rates = UPS_GROUND_ZONE_RATES[zone]
    return rates["base"] + (rates["per_lb"] * billable_weight)


def partnered_carrier_cost(weight_lb: float, zone: int) -> float:
    """Amazon Partnered Carrier (SPD) rate - discounted UPS via Seller Central."""
    return ups_ground_cost(weight_lb, zone) * (1 - PARTNERED_CARRIER_DISCOUNT)


def avg_inbound_shipping(
    weight_lb: float,
    units_per_box: int = 1,
    use_partnered: bool = True,
) -> float:
    """
    Weighted-average inbound shipping cost per unit from Christiansburg, VA.

    Amazon decides which FBA warehouse receives your inventory - you cannot
    pick. This averages across the most common destination zones, weighted
    by how often Amazon routes inventory there from the East Coast.
    """
    box_weight = weight_lb * units_per_box
    cost_fn = partnered_carrier_cost if use_partnered else ups_ground_cost

    weighted_cost = sum(
        cost_fn(box_weight, zone) * prob
        for zone, prob in DESTINATION_PROBABILITY.items()
    )

    return weighted_cost / units_per_box


def supplies_cost_per_unit(units_per_box: int = 1) -> float:
    """Polybag, label, box, tape amortized per unit."""
    box_cost = 1.50
    polybag_label = 0.15
    return polybag_label + (box_cost / units_per_box)

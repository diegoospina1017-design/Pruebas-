"""
Amazon FBA fee tables (2024-2025 rates).
Source: Amazon Seller Central fee schedules, US marketplace.
Update yearly - Amazon publishes new rates each January.
"""

REFERRAL_FEES = {
    "automotive": 0.12,
    "baby": 0.15,
    "beauty": 0.15,
    "beauty_under_10": 0.08,
    "books": 0.15,
    "camera_photo": 0.08,
    "cell_phones": 0.08,
    "clothing": 0.17,
    "computers": 0.08,
    "consumer_electronics": 0.08,
    "fine_art": 0.20,
    "grocery": 0.08,
    "grocery_over_15": 0.15,
    "health_personal_care": 0.15,
    "home_garden": 0.15,
    "industrial_scientific": 0.12,
    "jewelry": 0.20,
    "kitchen": 0.15,
    "lawn_garden": 0.15,
    "luggage": 0.15,
    "music": 0.15,
    "musical_instruments": 0.15,
    "office_products": 0.15,
    "outdoors": 0.15,
    "pet_supplies": 0.15,
    "shoes_handbags": 0.15,
    "software": 0.15,
    "sports": 0.15,
    "tools_home_improvement": 0.15,
    "toys_games": 0.15,
    "video_games": 0.15,
    "watches": 0.16,
    "default": 0.15,
}

MIN_REFERRAL_FEE = 0.30


def fba_fulfillment_fee(weight_lb: float, size_tier: str = "standard") -> float:
    """
    FBA fulfillment fee based on shipping weight and size tier.
    Rates effective 2024.
    """
    if size_tier == "small_standard":
        if weight_lb <= 0.25:
            return 3.06
        if weight_lb <= 0.5:
            return 3.15
        if weight_lb <= 0.75:
            return 3.24
        if weight_lb <= 1.0:
            return 3.34

    if size_tier == "standard":
        if weight_lb <= 0.25:
            return 3.86
        if weight_lb <= 0.5:
            return 4.08
        if weight_lb <= 0.75:
            return 4.24
        if weight_lb <= 1.0:
            return 4.75
        if weight_lb <= 1.5:
            return 5.40
        if weight_lb <= 2.0:
            return 5.69
        if weight_lb <= 2.5:
            return 6.10
        if weight_lb <= 3.0:
            return 6.39
        extra_lb = max(0, weight_lb - 3.0)
        return 6.92 + (0.32 * extra_lb)

    if size_tier == "large_bulky":
        if weight_lb <= 50:
            return 9.61 + (0.38 * weight_lb)
        return 26.33 + (0.38 * (weight_lb - 50))

    raise ValueError(f"Unknown size tier: {size_tier}")


def monthly_storage_fee(
    length_in: float,
    width_in: float,
    height_in: float,
    size_tier: str = "standard",
    months_held: float = 1.0,
    peak_season: bool = False,
) -> float:
    """
    Monthly storage fee. Peak season = Oct-Dec (much higher).
    """
    cubic_feet = (length_in * width_in * height_in) / 1728

    if size_tier in ("standard", "small_standard"):
        rate = 2.40 if peak_season else 0.78
    else:
        rate = 1.40 if peak_season else 0.56

    return cubic_feet * rate * months_held


def referral_fee(sale_price: float, category: str = "default") -> float:
    """Referral fee based on category percentage, with $0.30 minimum."""
    pct = REFERRAL_FEES.get(category, REFERRAL_FEES["default"])
    fee = sale_price * pct
    return max(fee, MIN_REFERRAL_FEE)

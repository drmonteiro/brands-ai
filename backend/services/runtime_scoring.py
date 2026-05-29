"""
Runtime scoring for pipeline N4 (score_and_save_node).

This module is the single source of truth for prospect ranking in production.
Offline evaluation uses rubric.yaml + evaluation/rubric_evaluator.py — not this file.

City-presence weight in final_score: see WEIGHT_* below (Fase 7.1 pending business OK).
"""

from typing import Optional, Tuple

# --- Final score weights (must sum to 1.0 when city_presence is enabled) ---
WEIGHT_SIMILARITY = 0.40
WEIGHT_LLM_FIT = 0.30
WEIGHT_PRICE = 0.15
WEIGHT_SIZE = 0.15

# Proposed after business approval (not applied yet):
# WEIGHT_CITY_PRESENCE = 0.15
# WEIGHT_SIMILARITY = 0.40
# WEIGHT_LLM_FIT = 0.25
# WEIGHT_PRICE = 0.10
# WEIGHT_SIZE = 0.10


def calculate_price_alignment_score(price_eur: float) -> float:
    """Suit price alignment 0-100 (€500-€1700 flat max). Unknown price → neutral 50."""
    price = float(price_eur or 0)
    if price == 0:
        return 50.0
    if 500 <= price <= 1700:
        return 100.0
    if 375 <= price < 500:
        return 30.0 + 70.0 * (price - 375) / 125
    if 1700 < price <= 2500:
        return 100.0 - 70.0 * (price - 1700) / 800
    return 10.0


def calculate_size_alignment_score(store_count: int) -> float:
    """Store count alignment 0-100 (1-20 flat max). Unknown → neutral 50."""
    stores = int(store_count or 0)
    if stores == 0:
        return 50.0
    if 1 <= stores <= 20:
        return 100.0
    if 20 < stores <= 30:
        return 100.0 - 70.0 * (stores - 20) / 10
    return 10.0


def calculate_city_presence_score(presence_type: Optional[str]) -> float:
    """
    City presence 0-100 for breakdown (HQ > store > showroom).
    Not included in compute_runtime_final_score until weights approved.
    """
    if presence_type is None:
        return 0.0
    p = presence_type.lower().strip()
    if p == "hq":
        return 100.0
    if p == "store":
        return 67.0
    if p == "showroom":
        return 40.0
    return 0.0


def compute_runtime_final_score(
    similarity_score: float,
    llm_fit_0_10: float,
    price_eur: float,
    store_count: int,
) -> Tuple[float, float, float, float]:
    """
    Returns (final_score, price_score, size_score, fit_pct_0_100).
    """
    price_score = calculate_price_alignment_score(price_eur)
    size_score = calculate_size_alignment_score(store_count)
    fit_pct = (float(llm_fit_0_10) / 10.0) * 100.0
    final = (
        WEIGHT_SIMILARITY * float(similarity_score)
        + WEIGHT_LLM_FIT * fit_pct
        + WEIGHT_PRICE * price_score
        + WEIGHT_SIZE * size_score
    )
    return round(final, 2), price_score, size_score, fit_pct

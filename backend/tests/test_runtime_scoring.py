"""Runtime scoring weights (N4) — not the offline rubric in scoring.py."""

from services.runtime_scoring import (
    WEIGHT_LLM_FIT,
    WEIGHT_PRICE,
    WEIGHT_SIMILARITY,
    WEIGHT_SIZE,
    calculate_city_presence_score,
    calculate_price_alignment_score,
    compute_runtime_final_score,
)


def test_weights_sum_to_one():
    assert abs(WEIGHT_SIMILARITY + WEIGHT_LLM_FIT + WEIGHT_PRICE + WEIGHT_SIZE - 1.0) < 1e-9


def test_final_score_mid_range_prospect():
    final, price_s, size_s, _ = compute_runtime_final_score(
        similarity_score=70.0,
        llm_fit_0_10=8.0,
        price_eur=900.0,
        store_count=3,
    )
    assert price_s == 100.0
    assert size_s == 100.0
    assert 60.0 < final < 85.0


def test_city_presence_breakdown_only():
    assert calculate_city_presence_score("hq") == 100.0
    assert calculate_city_presence_score("store") == 67.0
    assert calculate_price_alignment_score(0) == 50.0

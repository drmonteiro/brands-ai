"""N4 similarity failure must be visible, not silently scored as 50."""

import pytest
from unittest.mock import AsyncMock

from agents.nodes import persistence as persistence_mod


@pytest.mark.asyncio
async def test_similarity_failure_flags_degraded_run(monkeypatch):
    brands = [
        {"name": "Zephyr Tailors", "website_url": "https://zephyr-tailors.example", "avg_suit_price_eur": 800, "store_count": 3, "origin_country": "UK"},
        {"name": "Nimbus Menswear", "website_url": "https://nimbus-mens.example", "avg_suit_price_eur": 900, "store_count": 2, "origin_country": "UK"},
        {"name": "Quasar Boutique", "website_url": "https://quasar-boutique.example", "avg_suit_price_eur": 700, "store_count": 4, "origin_country": "UK"},
        {"name": "Orion Sartorial", "website_url": "https://orion-sartorial.example", "avg_suit_price_eur": 600, "store_count": 1, "origin_country": "UK"},
    ]

    async def _fail_similarity_batch(_texts, n_results=3):
        raise RuntimeError("embedding dimension mismatch")

    monkeypatch.setattr(persistence_mod, "find_similar_clients_batch", _fail_similarity_batch)
    monkeypatch.setattr(persistence_mod, "SIMILARITY_RETRY_DELAY_SEC", 0)
    monkeypatch.setattr(persistence_mod, "_llm_fit_assessment", AsyncMock(
        return_value=[{"url": b["website_url"], "fit_score": 7, "fit_reason": "ok"} for b in brands]
    ))
    monkeypatch.setattr(persistence_mod, "save_prospect", AsyncMock(return_value={"status": "skipped"}))
    monkeypatch.setattr(
        persistence_mod,
        "get_existing_urls_for_city",
        AsyncMock(return_value=set()),
    )
    monkeypatch.setattr(
        persistence_mod,
        "resolve_target_city_context",
        AsyncMock(return_value=persistence_mod.CityContext(
            query="Test", canonical_name="Test", names=["Test"], country="UK"
        )),
    )
    monkeypatch.setattr(persistence_mod, "should_exclude_brand_for_location", lambda _b, _c: False)

    state = {
        "target_city": "Test",
        "enriched_brands": brands,
        "exchange_rate": 1.08,
    }
    with pytest.raises(RuntimeError, match="nada foi guardado"):
        await persistence_mod.score_and_save_node(state)
    persistence_mod.save_prospect.assert_not_awaited()


async def test_empty_similarity_counts_as_failure_not_an_average_score(monkeypatch):
    async def _empty(_texts, n_results=3):
        return [[]]

    monkeypatch.setattr(persistence_mod, "find_similar_clients_batch", _empty)
    assert await persistence_mod._find_similar_with_retries(["x"]) == [[]]


async def test_similarity_retries_before_failing(monkeypatch):
    calls = {"n": 0}

    async def _flaky(_texts, n_results=3):
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("temporary")
        return [[{"similarity": 70}]]

    monkeypatch.setattr(persistence_mod, "SIMILARITY_RETRY_DELAY_SEC", 0)
    monkeypatch.setattr(persistence_mod, "find_similar_clients_batch", _flaky)
    assert await persistence_mod._find_similar_with_retries(["x"]) == [[{"similarity": 70}]]


def test_similarity_averages_the_closest_clients():
    assert persistence_mod._similarity_from_matches(
        [{"similarity": 70}, {"similarity": 60}, {"similarity": 50}]
    ) == 60

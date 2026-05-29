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

    async def _fail_similarity(_text, n_results=3):
        raise RuntimeError("embedding dimension mismatch")

    monkeypatch.setattr(persistence_mod, "find_similar_clients", _fail_similarity)
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
    out = await persistence_mod.score_and_save_node(state)

    assert out["similarity_degraded"] is True
    assert out["similarity_failure_count"] == 4
    assert any("RUN DEGRADADO" in m for m in out["progress"])
    assert any("Similaridade falhou" in m for m in out["progress"])

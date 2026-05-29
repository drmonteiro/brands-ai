"""Enrich skips full pipeline when brand_facts cache is fresh."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from agents.nodes import enrich as enrich_mod


@pytest.mark.asyncio
async def test_enrich_uses_cache_hit_path_only_places(monkeypatch):
    filtered = [{
        "url": "https://cached-brand.test",
        "brand_name": "Cached Brand",
        "title": "Cached Brand",
        "text": "discovery text",
        "highlights": "",
    }]

    fresh_facts = {
        "domain": "cached-brand.test",
        "name": "Cached Brand",
        "website_url": "https://cached-brand.test",
        "headquarters_city": "Milan",
        "headquarters_confidence": "verified",
        "avg_suit_price_eur": 900,
        "store_count": 3,
        "store_count_confidence": "verified",
        "store_locations": [],
        "updated_at": datetime.now(timezone.utc),
    }

    monkeypatch.setattr(
        enrich_mod,
        "get_brand_facts_batch",
        AsyncMock(return_value={"cached-brand.test": fresh_facts}),
    )
    monkeypatch.setattr(
        enrich_mod,
        "resolve_target_city_context",
        AsyncMock(return_value=enrich_mod.CityContext(
            query="Milan", canonical_name="Milan", names=["Milan"], country="Italy"
        )),
    )

    full_pipeline = AsyncMock()
    monkeypatch.setattr(enrich_mod, "_run_full_enrich_pipeline", full_pipeline)

    async def _local_only(brands, city_ctx, target_city, progress):
        for b in brands:
            b["local_store_address"] = "Shop, Milan"
            b["city_presence_type"] = "store"
        return brands, city_ctx

    monkeypatch.setattr(enrich_mod, "_enrich_cached_brands_local_only", _local_only)
    monkeypatch.setattr(enrich_mod, "upsert_brand_facts_from_brands", AsyncMock(return_value=0))

    out = await enrich_mod.enrich_node({
        "target_city": "Milan",
        "target_country": "Italy",
        "filtered_brands": filtered,
    })

    full_pipeline.assert_not_awaited()
    assert len(out["enriched_brands"]) == 1
    assert out["enriched_brands"][0]["avg_suit_price_eur"] == 900
    assert out["enriched_brands"][0]["local_store_address"] == "Shop, Milan"
    assert any("cache hit" in m for m in out["progress"])

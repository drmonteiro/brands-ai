"""Batched HQ knowledge fallback."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.location_enrichment import resolve_headquarters_via_llm_batch


@pytest.mark.asyncio
async def test_batch_hq_applies_only_high_confidence():
    mock_response = MagicMock()
    mock_response.content = """[
      {"headquarters_city": "London", "headquarters_address": null, "origin_country": "UK", "confidence": "high"},
      {"headquarters_city": "Paris", "headquarters_address": "1 Rue", "origin_country": "FR", "confidence": "unknown"}
    ]"""
    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = mock_response

    brands = [
        {"name": "Alpha", "website_url": "https://a.test"},
        {"name": "Beta", "website_url": "https://b.test"},
    ]

    with patch("services.location_enrichment._get_llm", return_value=mock_llm):
        out = await resolve_headquarters_via_llm_batch(brands)

    assert out[0]["headquarters_city"] == "London"
    assert out[0]["headquarters_confidence"] == "llm_knowledge"
    assert out[0]["headquarters_address"] is None
    assert out[1].get("headquarters_city") in (None, "Paris")
    if out[1].get("headquarters_city"):
        assert out[1]["headquarters_confidence"] != "llm_knowledge" or out[1]["headquarters_city"] != "Paris"

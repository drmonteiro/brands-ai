"""Google Places call B only when site store data is not verified."""

from unittest.mock import AsyncMock, patch

import pytest

from services import google_places as gp


@pytest.mark.asyncio
async def test_enrich_skips_count_when_site_stores_verified():
    with patch.object(gp, "search_local_presence", AsyncMock(return_value={"local_address": "1 High St"})) as mock_a, \
         patch.object(gp, "count_brand_locations", AsyncMock(return_value=[{"address": "x"}])) as mock_b:
        result = await gp.enrich_with_places(
            "Test Brand", "London", "UK", count_all_locations=False
        )

    mock_a.assert_awaited_once()
    mock_b.assert_not_awaited()
    assert result["places_store_count"] == 0
    assert result["places_locations"] == []


@pytest.mark.asyncio
async def test_enrich_runs_count_when_site_unknown():
    with patch.object(gp, "search_local_presence", AsyncMock(return_value=None)) as mock_a, \
         patch.object(gp, "count_brand_locations", AsyncMock(return_value=[
             {"name": "Test Brand", "address": "2 Low St"},
         ])) as mock_b:
        result = await gp.enrich_with_places(
            "Test Brand", "London", "UK", count_all_locations=True
        )

    mock_a.assert_awaited_once()
    mock_b.assert_awaited_once()
    assert result["places_store_count"] == 1
    assert result["places_locations"] == ["2 Low St"]

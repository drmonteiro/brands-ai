"""Unit tests for location enrichment: HQ, stores, merge, validation."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.location_enrichment import (
    merge_store_data,
    validate_location_data,
    resolve_headquarters_via_llm,
    _brand_name_matches,
    CityContext,
    city_name_matches_context,
    city_in_text,
    brand_has_city_presence,
    should_exclude_brand_for_location,
)


def vienna_ctx() -> CityContext:
    return CityContext(
        query="Viena",
        canonical_name="Vienna",
        names=["Vienna", "Wien", "Viena"],
        country="Austria",
    )


def london_ctx() -> CityContext:
    return CityContext(
        query="London",
        canonical_name="London",
        names=["London", "Londres"],
        country="United Kingdom",
    )


class TestCityContext:
    def test_vienna_name_matching(self):
        ctx = vienna_ctx()
        assert city_name_matches_context("Wien", ctx)
        assert city_name_matches_context("Vienna", ctx)
        assert city_name_matches_context("Viena", ctx)
        assert not city_name_matches_context("Hamburg", ctx)

    def test_llm_equivalence_cache(self):
        ctx = vienna_ctx()
        ctx.equivalence_cache["wien"] = True
        assert city_name_matches_context("Wien", ctx)

    def test_city_in_address(self):
        ctx = vienna_ctx()
        assert city_in_text(ctx, "1010 Wien, Austria")
        assert city_in_text(london_ctx(), "12 Savile Row, London W1")
        assert not city_in_text(vienna_ctx(), "102 High Rd, London N22")


class TestLocationFilter:
    def test_keep_vienna_hq_when_search_viena(self):
        ctx = vienna_ctx()
        brand = {
            "name": "KNIZE",
            "headquarters_city": "Wien",
            "headquarters_confidence": "verified",
            "city_presence_type": "store",
            "local_store_address": "1010 Wien, Austria",
        }
        assert brand_has_city_presence(brand, ctx)
        assert not should_exclude_brand_for_location(brand, ctx)

    def test_keep_store_in_city_hq_elsewhere(self):
        ctx = vienna_ctx()
        brand = {
            "name": "ANTON MEYER",
            "headquarters_city": "Hamburg",
            "headquarters_confidence": "verified",
            "city_presence_type": "store",
            "local_store_address": "Landstraßer Hauptstraße, Wien",
        }
        assert not should_exclude_brand_for_location(brand, ctx)

    def test_exclude_hq_elsewhere_no_presence(self):
        ctx = vienna_ctx()
        brand = {
            "name": "Hockerty",
            "headquarters_city": "Barcelona",
            "headquarters_confidence": "llm_knowledge",
            "city_presence_type": "unknown",
            "local_store_address": None,
            "store_locations": [],
        }
        assert should_exclude_brand_for_location(brand, ctx)

    def test_exclude_unknown_hq_no_local_presence(self):
        ctx = vienna_ctx()
        brand = {
            "name": "MASSNAHME",
            "headquarters_city": None,
            "headquarters_confidence": "unknown",
            "city_presence_type": "unknown",
            "local_store_address": None,
            "store_locations": [],
        }
        assert should_exclude_brand_for_location(brand, ctx)

    def test_exclude_false_positive_local_in_other_city(self):
        ctx = vienna_ctx()
        brand = {
            "name": "Happy Gentleman",
            "headquarters_city": None,
            "headquarters_confidence": "unknown",
            "city_presence_type": "store",
            "local_store_address": "102 High Rd, London N22",
            "store_locations": [],
        }
        assert not brand_has_city_presence(brand, ctx)
        assert should_exclude_brand_for_location(brand, ctx)

    def test_keep_unknown_hq_with_confirmed_vienna_store(self):
        ctx = vienna_ctx()
        brand = {
            "name": "Local Tailor",
            "headquarters_city": None,
            "headquarters_confidence": "unknown",
            "local_store_address": "Landstraßer Hauptstraße, 1030 Wien",
            "store_locations": [],
        }
        assert brand_has_city_presence(brand, ctx)
        assert not should_exclude_brand_for_location(brand, ctx)

    def test_validate_viena_vienna_hq(self):
        ctx = vienna_ctx()
        brand = {
            "headquarters_city": "Wien",
            "headquarters_confidence": "verified",
            "headquarters_address": "1010 Wien",
            "local_store_address": None,
            "store_locations": [],
        }
        result = validate_location_data(brand, ctx)
        assert result["city_presence_type"] == "hq"


class TestBrandNameMatches:
    def test_exact_match(self):
        assert _brand_name_matches("Richard James", "Richard James") is True

    def test_partial_match(self):
        assert _brand_name_matches("Richard James - Savile Row", "Richard James") is True

    def test_no_match(self):
        assert _brand_name_matches("Unrelated Shop", "Richard James") is False


class TestMergeStoreData:
    def test_site_priority(self):
        result = merge_store_data(
            site_addresses=["12 Savile Row, London", "45 Duke St, London"],
            site_count=2,
            site_confidence="verified",
            places_addresses=["99 Oxford St, London"],
            places_count=1,
        )
        assert result["store_count"] == 2
        assert result["store_count_confidence"] == "verified"
        assert len(result["store_locations"]) == 3

    def test_discrepancy_marks_uncertain(self):
        result = merge_store_data(
            site_addresses=["Store A"],
            site_count=2,
            site_confidence="verified",
            places_addresses=["Store B", "Store C", "Store D", "Store E"],
            places_count=4,
        )
        assert result["store_count_confidence"] == "uncertain"

    def test_places_only_estimated(self):
        result = merge_store_data(
            site_addresses=[],
            site_count=None,
            site_confidence="unknown",
            places_addresses=["1 Main St", "2 High St"],
            places_count=2,
        )
        assert result["store_count"] == 2
        assert result["store_count_confidence"] == "estimated"

    def test_no_data_unknown(self):
        result = merge_store_data([], None, "unknown", [], 0)
        assert result["store_count"] == 0
        assert result["store_count_confidence"] == "unknown"

    def test_deduplication(self):
        result = merge_store_data(
            site_addresses=["12 Savile Row, London"],
            site_count=1,
            site_confidence="verified",
            places_addresses=["12 Savile Row, London"],
            places_count=1,
        )
        assert len(result["store_locations"]) == 1


class TestValidateLocationData:
    def test_hq_in_target_city(self):
        ctx = london_ctx()
        brand = {
            "headquarters_city": "London",
            "headquarters_confidence": "verified",
            "headquarters_address": "12 Savile Row",
            "local_store_address": None,
            "store_locations": [],
        }
        result = validate_location_data(brand, ctx)
        assert result["city_presence_type"] == "hq"
        assert result["headquarters_address"] == "12 Savile Row"

    def test_store_only_not_hq(self):
        ctx = london_ctx()
        brand = {
            "headquarters_city": "Manchester",
            "headquarters_confidence": "verified",
            "headquarters_address": "1 Deansgate",
            "local_store_address": "10 Bond St, London",
            "store_locations": [],
        }
        result = validate_location_data(brand, ctx)
        assert result["city_presence_type"] == "store"

    def test_clears_unverified_hq_address(self):
        ctx = london_ctx()
        brand = {
            "headquarters_city": None,
            "headquarters_confidence": "unknown",
            "headquarters_address": "Wrong address from Places",
            "local_store_address": "10 Bond St, London",
            "store_locations": [],
        }
        result = validate_location_data(brand, ctx)
        assert result["headquarters_address"] is None
        assert result["city_presence_type"] == "store"

    def test_clears_llm_knowledge_hq_address(self):
        ctx = london_ctx()
        brand = {
            "headquarters_city": "London",
            "headquarters_confidence": "llm_knowledge",
            "headquarters_address": "12 Savile Row",
            "local_store_address": None,
            "store_locations": [],
        }
        result = validate_location_data(brand, ctx)
        assert result["headquarters_address"] is None
        assert result["city_presence_type"] == "hq"

    def test_clears_local_store_wrong_city(self):
        ctx = vienna_ctx()
        brand = {
            "headquarters_city": None,
            "headquarters_confidence": "unknown",
            "local_store_address": "102 High Rd, London N22",
            "store_locations": [],
        }
        result = validate_location_data(brand, ctx)
        assert result["local_store_address"] is None
        assert result["city_presence_type"] == "unknown"

    def test_hq_not_from_places_address(self):
        ctx = london_ctx()
        brand = {
            "headquarters_city": None,
            "headquarters_confidence": "unknown",
            "headquarters_address": None,
            "local_store_address": "10 Bond St, London",
            "store_locations": [],
        }
        result = validate_location_data(brand, ctx)
        assert result.get("headquarters_address") is None
        assert result["local_store_address"] == "10 Bond St, London"


@pytest.mark.asyncio
async def test_llm_hq_fallback_returns_null_when_unsure():
    mock_response = MagicMock()
    mock_response.content = '{"headquarters_city": null, "headquarters_address": null, "origin_country": null, "confidence": "unknown"}'

    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = mock_response

    with patch("services.location_enrichment._get_llm", return_value=mock_llm):
        result = await resolve_headquarters_via_llm("Unknown Brand XYZ", "https://unknown.test")

    assert result["headquarters_city"] is None
    assert result["headquarters_confidence"] == "unknown"


@pytest.mark.asyncio
async def test_llm_hq_fallback_returns_city_only_when_confident():
    mock_response = MagicMock()
    mock_response.content = (
        '{"headquarters_city": "London", "headquarters_address": "12 Savile Row", '
        '"origin_country": "United Kingdom", "confidence": "high"}'
    )

    mock_llm = AsyncMock()
    mock_llm.ainvoke.return_value = mock_response

    with patch("services.location_enrichment._get_llm", return_value=mock_llm):
        result = await resolve_headquarters_via_llm("Richard James", "https://richardjames.test")

    assert result["headquarters_city"] == "London"
    assert result["headquarters_address"] is None
    assert result["headquarters_confidence"] == "llm_knowledge"

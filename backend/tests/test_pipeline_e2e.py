"""
End-to-end pipeline test: discovery → filter → enrich → score_save

Mocks external services (Exa, LLM, Google Places, DB) and verifies
the 4-node pipeline completes without errors.
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple
from unittest.mock import AsyncMock

import pytest

import agents.nodes.discovery as discovery_mod
import agents.nodes.filter as filter_mod
import agents.nodes.enrich as enrich_mod
import agents.nodes.persistence as persistence_mod


LONDON_FIXTURE_BRANDS = [
    ("https://cadandthedandy.test", "Cad And The Dandy"),
    ("https://richardjames.test", "Richard James"),
    ("https://nortonandsons.test", "Norton And Sons"),
    ("https://grahambrown.test", "Graham Brown Tailors"),
    ("https://henrypoole.test", "Henry Poole"),
]


def _exa_text(title: str) -> str:
    core = (
        f"{title} — independent premium menswear and tailoring in London. "
        "Bespoke and sartorial suits, jackets, trousers. Heritage craftsmanship. "
        "Shop now. Suits from €995 £850 view collection."
    )
    return (core + "\n") * 20


def _mock_discovery_raw() -> List[Dict]:
    return [
        {"url": url, "title": title, "text": _exa_text(title), "highlights": ""}
        for url, title in LONDON_FIXTURE_BRANDS
    ]


async def _mock_filter_batch(candidates, target_city):
    return [
        {"url": c["url"], "keep": True, "brand_name": c.get("title", ""), "reason": "mock"}
        for c in candidates
    ]


async def _mock_extract_structured_batch(brands, target_city, target_country):
    return [
        {
            "name": b.get("brand_name", ""),
            "website_url": b["url"],
            "origin_country": "United Kingdom",
            "avg_suit_price_eur": 900,
            "price_range_min_eur": 700,
            "price_range_max_eur": 1200,
            "price_note": "Suits from £700",
            "made_to_measure": True,
            "wool_percentage": "100%",
            "brand_style": "Heritage/Premium",
            "business_model": "Retail",
            "company_overview": f"{b.get('brand_name', '')} premium menswear in London.",
            "clothing_types": ["suits", "blazers"],
            "target_gender": "men",
            "is_chain": False,
            "bespoke_only": False,
        }
        for b in brands
    ]


async def _mock_enrich_with_places(brand_name, city, country="", website_url=""):
    return {
        "places_address": f"{brand_name}, 1 Savile Row, London",
        "places_phone": "+44 20 0000 0000",
        "places_store_count": 3,
        "places_locations": [f"{brand_name} flagship, London"],
        "places_rating": 4.5,
        "places_review_count": 120,
        "places_maps_url": None,
        "places_website": None,
    }


async def _mock_find_similar(text, n_results=3):
    return [{"similarity": 78.0, "name": "Hawes & Curtis", "id": "c0", "country": "UK", "metadata": {}, "profile": ""}]


async def _mock_llm_fit(brands, target_city):
    return [
        {"url": b.get("website_url", ""), "fit_score": 8, "fit_reason": "mock fit"}
        for b in brands
    ]


@pytest.mark.asyncio
async def test_simplified_pipeline_e2e(monkeypatch):
    saved: List[Dict] = []

    async def _track_save(prospect, city, scores, similar_clients=None):
        saved.append({"prospect": prospect, "city": city, "scores": scores})
        return {"status": "saved", "id": "mock-id", "prospect": prospect}

    # Mock discovery internals
    monkeypatch.setattr(
        "agents.nodes.discovery._infer_country",
        AsyncMock(return_value="United Kingdom"),
    )
    monkeypatch.setattr(
        "agents.nodes.discovery._generate_queries",
        AsyncMock(return_value=["men's suit brands London"]),
    )

    async def _fake_exa_search(exa, query, kwargs):
        class MockResult:
            def __init__(self, url, title, text):
                self.url = url
                self.title = title
                self.text = text
                self.highlights = []
        class MockResponse:
            def __init__(self):
                self.results = [MockResult(u, t, _exa_text(t)) for u, t in LONDON_FIXTURE_BRANDS]
        return MockResponse()

    monkeypatch.setattr("agents.nodes.discovery._exa_search_with_retries", _fake_exa_search)
    monkeypatch.setattr("agents.nodes.discovery.Exa", lambda api_key: None)

    # Mock filter
    monkeypatch.setattr("agents.nodes.filter._filter_batch", _mock_filter_batch)

    # Mock enrich
    monkeypatch.setattr("agents.nodes.enrich._extract_structured_batch", _mock_extract_structured_batch)
    monkeypatch.setattr("agents.nodes.enrich.enrich_with_places", _mock_enrich_with_places)

    # Mock persistence
    monkeypatch.setattr("agents.nodes.persistence.find_similar_clients", _mock_find_similar)
    monkeypatch.setattr("agents.nodes.persistence._llm_fit_assessment", _mock_llm_fit)
    monkeypatch.setattr("agents.nodes.persistence.save_prospect", _track_save)
    monkeypatch.setattr(
        "agents.nodes.persistence.get_existing_urls_for_city",
        AsyncMock(return_value=set()),
    )

    # Run pipeline nodes sequentially
    init_state = {
        "target_city": "London",
        "target_country": "",
        "exchange_rate": 1.08,
        "search_results_raw": [],
        "filtered_brands": [],
        "enriched_brands": [],
        "verified_brands": [],
        "progress": [],
        "error": None,
    }

    # Node 1: Discovery
    disc_out = await discovery_mod.discovery_node(init_state)
    assert disc_out["target_country"] == "United Kingdom"
    assert len(disc_out["search_results_raw"]) == len(LONDON_FIXTURE_BRANDS)

    # Node 2: Filter
    filter_state = {**init_state, **disc_out}
    filter_out = await filter_mod.filter_node(filter_state)
    assert len(filter_out["filtered_brands"]) == len(LONDON_FIXTURE_BRANDS)

    # Node 3: Enrich
    enrich_state = {**filter_state, **filter_out}
    enrich_out = await enrich_mod.enrich_node(enrich_state)
    assert len(enrich_out["enriched_brands"]) == len(LONDON_FIXTURE_BRANDS)
    for b in enrich_out["enriched_brands"]:
        assert b.get("store_count", 0) > 0

    # Node 4: Score + Save
    score_state = {**enrich_state, **enrich_out}
    final_out = await persistence_mod.score_and_save_node(score_state)

    assert len(saved) == len(LONDON_FIXTURE_BRANDS)
    assert len(final_out["verified_brands"]) == len(LONDON_FIXTURE_BRANDS)
    for row in saved:
        assert row["scores"]["final_score"] > 0

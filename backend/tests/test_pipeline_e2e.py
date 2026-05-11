"""
End-to-end pipeline test: initialize → discovery (mock Exa) → validation (mock LLM / Places)
→ persistence (mock DB).

Ensures BrandLead accepts JSON nulls from deep analysis (Task 5) and the graph completes
without ValidationError.
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple
from unittest.mock import AsyncMock

import pytest

import agents.nodes.discovery as discovery_mod
import agents.nodes.initializer as initializer_mod
import agents.nodes.persistence as persistence_mod
import agents.nodes.validator as validator_mod
from evaluation.rubric_evaluator import evaluate_city, report_to_markdown
from models import QuerySearchResults


LONDON_FIXTURE_URLS: List[Tuple[str, str]] = [
    ("https://cadandthedandy.pipeline.test", "Cad And The Dandy Pipeline"),
    ("https://richardjames.pipeline.test", "Richard James Pipeline"),
    ("https://nortonandsons.pipeline.test", "Norton And Sons Pipeline"),
    ("https://grahambrown.pipeline.test", "Graham Brown Tailors Pipeline"),
    ("https://henrypoole.pipeline.test", "Henry Poole Pipeline"),
]


def _exa_body(title: str) -> str:
    """Long enough for Exa triage (>500) with keyword + pricing signals."""
    core = (
        f"{title} — independent premium menswear and tailoring in London Mayfair. "
        "Bespoke and sartorial suits, jackets, trousers. Heritage craftsmanship. "
        "Shop now add to cart. Suits from €995 £850 view collection product details. "
        "Our London showroom address in Savile Row."
    )
    return (core + "\n") * 40


def _mock_discovery_state(state: Dict[str, Any]) -> Dict[str, Any]:
    results: List[Dict[str, str]] = []
    for url, title in LONDON_FIXTURE_URLS:
        results.append(
            {
                "url": url,
                "title": title,
                "text": _exa_body(title),
                "content": "",
                "query_origin": "Local",
            }
        )
    search_results = [
        QuerySearchResults(
            query_index=0,
            query="mock london boutiques",
            query_origin="Local",
            results=results,
        )
    ]
    return {
        "candidate_urls": [r["url"] for r in results],
        "search_results": search_results,
        "progress": ["mock discovery"],
    }


async def _mock_triage_batch(contents, target_city: str):
    return [
        {
            "url": c.url,
            "score": 8,
            "reason": "mock triage",
            "is_menswear": True,
            "estimated_price_tier": "premium",
            "estimated_stores": "independent_1_20",
            "is_chain": False,
            "city_match": True,
            "is_bespoke_only": False,
            "appointment_only": False,
            "prices_visible": True,
        }
        for c in contents
    ]


async def _mock_places(brand_name: str, city: str, country: str):
    return {
        "places_address": f"{brand_name} Ltd, 1 Savile Row, {city}",
        "places_phone": "+44 20 0000 0000",
        "places_store_count": 2,
        "places_locations": [f"{brand_name} flagship, {city}"],
    }


async def _mock_deep_batch(
    extracted_contents, price_threshold_usd: float, target_city: str
):
    by_url = {u: t for u, t in LONDON_FIXTURE_URLS}
    out: List[Dict[str, Any]] = []
    for e in extracted_contents:
        title = by_url.get(e.url, "Unknown Brand")
        out.append(
            {
                "name": title,
                "url": e.url,
                "storeCount": 2,
                "isChain": False,
                "avgPrice": 1200.0,
                "avgJacketPrice": None,
                "avgTrousersPrice": None,
                "priceSource": "found",
                "priceNote": "",
                "woolPercentage": None,
                "madeToMeasure": None,
                "bespokeOnly": None,
                "appointmentOnly": None,
                "pricesVisible": True,
                "brandStyle": "Classic premium menswear",
                "businessModel": "Retail",
                "detailedDescription": f"{title} — high-quality menswear in {target_city}.",
                "headquartersAddress": f"Headquarters in London — {title}",
                "storeLocations": [f"12 Bond Street, {target_city}"],
                "whySelected": "mock deep analysis",
                "city": target_city,
                "country": "United Kingdom",
                "locationQuality": "premium",
                "fitScore": 85,
                "hasHeadquarters": True,
                "contactName": None,
                "contactRole": None,
                "contactEmail": None,
                "contactPhone": None,
            }
        )
    return out


async def _mock_similarity_embedding(text: str, n_results: int = 1):
    return [{"similarity": 78.0, "name": "Golden Client Mock"}]


async def _mock_score(prospect: Dict) -> Tuple[Dict, List]:
    return (
        {
            "final_score": 72.0,
            "passes_hard_filters": True,
            "rejection_reason": None,
            "breakdown": {
                "quality_score": 10,
                "similarity_score": 15,
                "location_score": 5,
            },
            "explanation": {
                "most_similar_client": "Mock Client",
                "similarity_explanation": "mock explanation",
            },
        },
        [],
    )


@pytest.mark.asyncio
async def test_london_pipeline_merged_null_llm_fields_saves(monkeypatch):
    saved: List[Dict] = []

    async def _track_save(prospect, city, scores, similar_clients=None):
        saved.append({"prospect": prospect, "city": city, "scores": scores})
        return {"status": "saved", "id": "mock-id", "prospect": prospect}

    monkeypatch.setattr(
        "agents.nodes.initializer.get_prospects_by_city",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        "agents.nodes.initializer.infer_country",
        AsyncMock(return_value="United Kingdom"),
    )
    monkeypatch.setattr(
        "agents.nodes.initializer.infer_city_languages",
        AsyncMock(return_value=["en"]),
    )
    monkeypatch.setattr(
        "agents.nodes.initializer.select_queries",
        AsyncMock(return_value=(["tailors London"], ["Local"], ["en"])),
    )
    monkeypatch.setattr(
        "agents.nodes.initializer.get_exchange_rate",
        AsyncMock(return_value=1.08),
    )

    async def _fake_discovery(_state):
        return _mock_discovery_state(_state if isinstance(_state, dict) else {})

    monkeypatch.setattr(
        "agents.nodes.discovery.discovery_node",
        _fake_discovery,
    )

    monkeypatch.setattr(
        "agents.nodes.validator.triage_batch",
        _mock_triage_batch,
    )
    monkeypatch.setattr(
        "agents.nodes.validator.deep_analyze_batch",
        _mock_deep_batch,
    )
    monkeypatch.setattr(
        "agents.nodes.validator.enrich_with_places",
        _mock_places,
    )
    monkeypatch.setattr(
        "agents.nodes.validator.find_similar_clients",
        _mock_similarity_embedding,
    )

    async def _idem_enrich(scored):
        return scored

    monkeypatch.setattr(
        "agents.nodes.validator.enrich_content_with_prices",
        _idem_enrich,
    )
    monkeypatch.setattr(
        "agents.nodes.validator.batch_extract_content",
        AsyncMock(return_value=[]),
    )
    monkeypatch.setattr(
        "agents.nodes.validator.is_domain_suppressed",
        AsyncMock(return_value=False),
    )

    monkeypatch.setattr(
        "agents.nodes.persistence.calculate_prospect_score",
        _mock_score,
    )
    monkeypatch.setattr(
        "agents.nodes.persistence.save_prospect",
        _track_save,
    )
    monkeypatch.setattr(
        "agents.nodes.persistence.get_existing_urls_for_city",
        AsyncMock(return_value=set()),
    )
    monkeypatch.setattr(
        "agents.nodes.persistence.find_contacts_for_brand",
        AsyncMock(return_value={}),
    )

    init_state = {
        "target_city": "London",
        "target_country": "USA",
        "price_threshold_eur": 500,
        "force_refresh": True,
        "search_queries": [],
        "search_results": [],
        "candidate_urls": [],
        "potential_brands": [],
        "verified_brands": [],
        "progress": [],
    }

    init_out = await initializer_mod.initialize_search(init_state)
    assert init_out.get("cached") is not True

    disc_out = await discovery_mod.discovery_node({**init_state, **init_out})  # type: ignore[arg-type]

    val_state = {
        **init_state,
        **init_out,
        **disc_out,
        "target_country": "United Kingdom",
    }
    val_out = await validator_mod.validation_node(val_state)

    potential = val_out.get("potential_brands") or []
    assert len(potential) == len(LONDON_FIXTURE_URLS)
    for lead in potential:
        assert getattr(lead, "made_to_measure", False) is None
        assert getattr(lead, "wool_percentage", "") is None
        unknown = getattr(lead, "_llm_unknown_fields", [])
        assert "made_to_measure" in unknown
        assert "wool_percentage" in unknown

    persist_state = {
        **val_state,
        **val_out,
        "exchange_rate": init_out["exchange_rate"],
    }
    fin = await persistence_mod.filter_node(persist_state)

    assert len(saved) == len(LONDON_FIXTURE_URLS)
    assert fin["verified_brands"]
    assert len(fin["verified_brands"]) == len(LONDON_FIXTURE_URLS)
    for row in saved:
        assert row["prospect"].get("made_to_measure") is None
        assert row["prospect"].get("wool_percentage") is None

    rubric_brands = [b.model_dump(by_alias=False) for b in fin["verified_brands"]]
    for b, s in zip(rubric_brands, saved):
        b["final_score"] = s["scores"].get("final_score")
    rubric_report = evaluate_city(rubric_brands, "London")
    assert rubric_report["total_brands"] == len(LONDON_FIXTURE_URLS)
    md = report_to_markdown(rubric_report)
    assert "Rubric Evaluation Report — London" in md

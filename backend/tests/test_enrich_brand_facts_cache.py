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
        "price_status": "confirmed",
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


async def test_contacts_only_looked_up_for_new_leads_and_saved(monkeypatch):
    from agents.nodes import persistence as persistence_mod

    new = {"website_url": "https://new.test", "name": "New"}
    existing = {"website_url": "https://www.old.test/", "name": "Old"}
    seen = []

    async def _attach(brands):
        seen.extend(brands)
        brands[0]["linkedin_contacts"] = [{"name": "A"}]
        return 1

    save = AsyncMock(return_value=1)
    monkeypatch.setattr(persistence_mod, "attach_linkedin_contacts", _attach)
    monkeypatch.setattr(persistence_mod, "save_brand_linkedin_contacts", save)

    found = await persistence_mod._attach_contacts_to_new_leads(
        [new, existing], {persistence_mod.normalize_url(existing["website_url"])}
    )

    assert seen == [new]
    assert found == 1
    save.assert_awaited_once_with([new])


async def test_contact_failure_does_not_lose_leads(monkeypatch):
    from agents.nodes import persistence as persistence_mod

    monkeypatch.setattr(persistence_mod, "attach_linkedin_contacts", AsyncMock(side_effect=RuntimeError("x")))
    assert await persistence_mod._attach_contacts_to_new_leads([{"website_url": "https://a.test"}], set()) == 0


async def test_facts_from_before_evidence_are_enriched_again(monkeypatch):
    filtered = [{"url": "https://old.test", "brand_name": "Old", "title": "Old", "text": "t", "highlights": ""}]
    old_facts = {"domain": "old.test", "name": "Old", "website_url": "https://old.test", "updated_at": datetime.now(timezone.utc)}
    monkeypatch.setattr(enrich_mod, "get_brand_facts_batch", AsyncMock(return_value={"old.test": old_facts}))
    monkeypatch.setattr(
        enrich_mod,
        "resolve_target_city_context",
        AsyncMock(return_value=enrich_mod.CityContext(query="Milan", canonical_name="Milan", names=["Milan"], country="Italy")),
    )

    async def _full(brands, city, country, ctx, progress):
        for b in brands:
            b["website_url"] = b["url"]
        return brands, ctx

    full = AsyncMock(side_effect=_full)
    monkeypatch.setattr(enrich_mod, "_run_full_enrich_pipeline", full)
    monkeypatch.setattr(enrich_mod, "upsert_brand_facts_from_brands", AsyncMock(return_value=0))
    await enrich_mod.enrich_node({"target_city": "Milan", "target_country": "Italy", "filtered_brands": filtered})
    full.assert_awaited_once()


def test_evidence_is_checked_against_the_brands_own_text():
    brand = {"website_url": "https://b.test", "text": "We make bespoke suits. Two-piece suit €1.200."}
    extracted = {
        "suit_prices": [{"amount": "1.200", "currency": "EUR", "product": "two-piece suit",
                         "quote": "Two-piece suit €1.200", "source_url": "https://b.test"}],
        "suit_evidence_quote": "We make bespoke suits",
    }
    enrich_mod._apply_evidence(brand, extracted, {})
    assert brand["avg_suit_price_eur"] == 1200
    assert brand["suit_evidence_verified"] is True

    enrich_mod._apply_evidence(brand, {"suit_evidence_quote": "Invented sentence not on site"}, {})
    assert brand["price_status"] == "unconfirmed"
    assert brand["suit_evidence_verified"] is False


def test_confirmed_suit_price_is_proof_of_selling_suits():
    brand = {"website_url": "https://b.test", "text": "Zweiteiler Anzug ab €1.200."}
    extracted = {
        "suit_prices": [{"amount": "1.200", "currency": "EUR", "product": "Anzug",
                         "quote": "Anzug ab €1.200", "source_url": "https://b.test"}],
        "suit_evidence_quote": "paraphrase that is not on the page",
    }
    enrich_mod._apply_evidence(brand, extracted, {})
    assert brand["suit_evidence_verified"] is True


def test_skipped_brand_does_not_shift_data_onto_the_next_brand():
    brands = [{"brand_name": "A", "url": "https://a.test"}, {"brand_name": "B", "url": "https://b.test"}, {"brand_name": "C", "url": "https://c.test"}]
    rows = [{"i": 1, "name": "A"}, {"i": 3, "name": "C"}]  # the LLM skipped B
    aligned = enrich_mod._align_extraction(rows, brands)
    assert [r["name"] for r in aligned] == ["A", "B", "C"]
    assert aligned[1]["_extraction_failed"] is True
    assert "_extraction_failed" not in aligned[2]


async def test_extraction_prompt_and_results_are_numbered(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    llm = MagicMock()
    llm.ainvoke = AsyncMock(return_value=SimpleNamespace(content='[{"i": 2, "name": "Second"}, {"i": 1, "name": "First"}]'))
    monkeypatch.setattr(enrich_mod, "get_llm_for_task", lambda task: llm)
    brands = [{"brand_name": "First", "url": "https://a.test"}, {"brand_name": "Second", "url": "https://b.test"}]
    out = await enrich_mod._extract_structured_batch(brands, [{}, {}], "London", "UK")
    assert [r["name"] for r in out] == ["First", "Second"]

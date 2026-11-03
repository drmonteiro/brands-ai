"""The quality gate: what the client said a great lead is."""

import pytest

from services.lead_gate import evaluate_lead


def _lead(**overrides):
    return {
        "core_category": "tailoring_core",
        "suit_evidence_verified": True,
        "target_gender": "men",
        "is_chain": False,
        "store_count": 3,
        "price_status": "confirmed",
        "avg_suit_price_eur": 900,
        "similarity_score": 60,
        "client_level": "same",
        "llm_fit_score": 8,
        "made_to_measure": True,
        **overrides,
    }


def test_great_lead_is_accepted():
    decision = evaluate_lead(_lead())
    assert decision.accepted is True and decision.code is None


@pytest.mark.parametrize("overrides,code", [
    ({"core_category": "casual_menswear"}, "not_suit_brand"),  # the client's T-shirt and jeans brands
    ({"core_category": "menswear_suits_minor"}, "not_suit_brand"),
    ({"core_category": "womenswear"}, "not_suit_brand"),
    ({"core_category": "hire_only"}, "not_suit_brand"),
    ({"core_category": "uniforms"}, "not_suit_brand"),
    ({"core_category": "accessories"}, "not_suit_brand"),
    ({"core_category": None}, "not_suit_brand"),
    ({"suit_evidence_verified": False}, "no_suit_evidence"),
    ({"suit_evidence_verified": None}, "no_suit_evidence"),
    ({"target_gender": "women"}, "womenswear_only"),
    ({"is_chain": True}, "chain"),
    ({"store_count": 31}, "too_many_stores"),
    ({"avg_suit_price_eur": 374}, "price_too_low"),
    ({"avg_suit_price_eur": 2501}, "price_too_high"),
    ({"avg_suit_price_eur": 200, "price_range_min_eur": 100, "price_range_max_eur": 374}, "price_too_low"),
    ({"avg_suit_price_eur": 3000, "price_range_min_eur": 2600, "price_range_max_eur": 3500}, "price_too_high"),
    ({"similarity_failed": True}, "similarity_failed"),
    ({"client_level": None}, "level_unknown"),
    ({"client_level": "below"}, "wrong_level"),
    ({"client_level": "different_category"}, "wrong_level"),
    ({"llm_fit_score": 5}, "wrong_level"),
    ({"_extraction_failed": True}, "extraction_failed"),
])
def test_rejections(overrides, code):
    decision = evaluate_lead(_lead(**overrides))
    assert decision.accepted is False
    assert decision.code == code
    assert decision.reason


@pytest.mark.parametrize("overrides", [
    {"store_count": 30},  # real client Hawes & Curtis
    {"store_count": 29},  # real client Grupo YES
    {"avg_suit_price_eur": 375},  # real client Sastrerías Españolas
    {"avg_suit_price_eur": 2500},
    {"core_category": "menswear_suits_prominent"},  # real client Hawes & Curtis
    {"target_gender": "unisex"},
    {"client_level": "above"},  # a €1500 tailor is inside the validated price band
    {"avg_suit_price_eur": 2235, "price_range_min_eur": 1140, "price_range_max_eur": 4089},  # MTM plus bespoke
    {"avg_suit_price_eur": 350, "price_range_min_eur": 300, "price_range_max_eur": 400},  # range reaches the band
])
def test_rule_boundaries_are_accepted(overrides):
    assert evaluate_lead(_lead(**overrides)).accepted is True


UNCONFIRMED = {"price_status": "unconfirmed", "avg_suit_price_eur": None}


def test_no_price_stays_when_clearly_at_client_level():
    assert evaluate_lead(_lead(**UNCONFIRMED, llm_fit_score=7, similarity_score=47)).accepted is True


@pytest.mark.parametrize("overrides,code", [
    ({"llm_fit_score": 6}, "unconfirmed_price_weak_fit"),
    ({"similarity_score": 46}, "unconfirmed_price_weak_fit"),
    ({"core_category": "menswear_suits_prominent", "made_to_measure": False}, "unconfirmed_price_weak_fit"),
    ({"client_level": "above"}, "wrong_level"),  # nothing shows it's within reach without a price
])
def test_no_price_is_rejected_without_strong_fit(overrides, code):
    decision = evaluate_lead(_lead(**UNCONFIRMED, **overrides))
    assert decision.accepted is False
    assert decision.code == code


def test_unconfirmed_ignores_any_stale_price_value():
    lead = _lead(price_status="unconfirmed", avg_suit_price_eur=50)
    assert evaluate_lead(lead).accepted is True


def test_directory_or_article_pages_are_rejected():
    assert evaluate_lead(_lead(is_official_site=False)).code == "not_official_site"
    assert evaluate_lead(_lead(is_official_site=True)).accepted is True


def test_same_brand_on_several_urls_keeps_the_best():
    from agents.nodes.persistence import _apply_quality_gate

    brands = [
        _lead(name="Gotstyle", website_url="https://gotstyle.ca", final_score=60),
        _lead(name="GOTSTYLE", website_url="https://gotstyle.com", final_score=80),
        _lead(name="Other", website_url="https://other.test", final_score=50),
    ]
    accepted, rejections = _apply_quality_gate(brands)
    assert [b["website_url"] for b in accepted] == ["https://gotstyle.com", "https://other.test"]
    assert [r["code"] for r in rejections] == ["duplicate_brand"]


def test_rejections_explain_why():
    from agents.nodes.persistence import _apply_quality_gate

    _, rejections = _apply_quality_gate([_lead(name="Jeans Co", website_url="https://j.test", core_category="casual_menswear")])
    assert rejections[0]["stage"] == "gate"
    assert rejections[0]["code"] == "not_suit_brand"
    assert "casual_menswear" in rejections[0]["reason"]


async def test_accented_client_name_is_still_recognised_as_a_client(monkeypatch):
    from unittest.mock import AsyncMock

    from agents.nodes import persistence as p

    monkeypatch.setattr(p, "find_similar_clients_batch", AsyncMock(return_value=[[{"similarity": 70, "name": "x"}]]))
    monkeypatch.setattr(p, "_llm_fit_assessment", AsyncMock(return_value=[]))
    monkeypatch.setattr(p, "save_prospect", AsyncMock())
    monkeypatch.setattr(p, "get_existing_urls_for_city", AsyncMock(return_value=set()))
    monkeypatch.setattr(p, "should_exclude_brand_for_location", lambda _b, _c: False)
    monkeypatch.setattr(
        p,
        "resolve_target_city_context",
        AsyncMock(return_value=p.CityContext(query="Madrid", canonical_name="Madrid", names=["Madrid"], country="Spain")),
    )
    out = await p.score_and_save_node({
        "target_city": "Madrid",
        "exchange_rate": 1.08,
        "enriched_brands": [{"name": "GARCÍA MADRID", "website_url": "https://www.garciamadrid.com/"}],
    })
    assert out["verified_brands"] == []
    assert any("clientes Lança" in m for m in out["progress"])
    p.save_prospect.assert_not_awaited()

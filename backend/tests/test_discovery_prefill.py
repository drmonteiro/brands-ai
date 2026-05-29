"""Discovery prefill — regex/heuristics without LLM."""

from services.discovery_prefill import (
    extract_email_from_text,
    extract_hq_city_from_text,
    extract_price_hints_from_text,
    prefill_from_discovery,
)


def test_extract_email_prefers_contact():
    text = "Reach us at noreply@x.com or contact@boutique.co.uk for appointments."
    assert extract_email_from_text(text) == "contact@boutique.co.uk"


def test_extract_hq_explicit_phrase():
    text = "Heritage tailoring brand based in Milan, Italy. Shop suits online."
    assert extract_hq_city_from_text(text) == "Milan"


def test_extract_price_gbp_to_eur():
    text = "Classic suits from £850. Bespoke jackets available."
    hints = extract_price_hints_from_text(text)
    assert hints["avg_suit_price_eur"] is not None
    assert hints["price_range_min_eur"] >= 900


def test_prefill_from_discovery_brand_dict():
    brand = {
        "text": "Cad And The Dandy — based in London. Suits from £995. Email: sales@cadandthedandy.co.uk",
        "highlights": "",
    }
    pre = prefill_from_discovery(brand)
    assert pre.get("contact_email") == "sales@cadandthedandy.co.uk"
    assert pre.get("headquarters_city") == "London"
    assert pre.get("headquarters_confidence") == "verified"

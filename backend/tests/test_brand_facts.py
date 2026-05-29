"""brand_facts cache — freshness, apply, and row extraction."""

from datetime import datetime, timedelta, timezone

from services.brand_facts import (
    apply_brand_facts_to_brand,
    brand_dict_to_facts_row,
    is_brand_facts_fresh,
)


def test_is_fresh_within_ttl():
    recent = datetime.now(timezone.utc) - timedelta(days=5)
    assert is_brand_facts_fresh(recent, ttl_days=30) is True


def test_is_stale_outside_ttl():
    old = datetime.now(timezone.utc) - timedelta(days=40)
    assert is_brand_facts_fresh(old, ttl_days=30) is False


def test_apply_brand_facts_sets_cache_hit_flag():
    brand = {"url": "https://example.com/page", "website_url": "https://example.com/page"}
    facts = {
        "domain": "example.com",
        "name": "Example Co",
        "website_url": "https://example.com",
        "headquarters_city": "Milan",
        "headquarters_confidence": "verified",
        "contact_email": "info@example.com",
        "avg_suit_price_eur": 950.0,
        "store_count": 4,
        "store_count_confidence": "verified",
        "store_locations": ["Via Roma 1, Milan"],
        "updated_at": datetime.now(timezone.utc),
    }
    apply_brand_facts_to_brand(brand, facts)
    assert brand["_brand_facts_cache_hit"] is True
    assert brand["avg_suit_price_eur"] == 950.0
    assert brand["contact_email"] == "info@example.com"
    assert brand["_site_store_confidence"] == "verified"


def test_brand_dict_to_facts_row_uses_domain_key():
    brand = {
        "website_url": "https://www.brand.co.uk/shops",
        "name": "Brand UK",
        "avg_suit_price_eur": 800,
        "store_count": 2,
        "store_count_confidence": "verified",
        "headquarters_city": "London",
        "headquarters_confidence": "llm_knowledge",
    }
    row = brand_dict_to_facts_row(brand)
    assert row is not None
    assert row["domain"] == "brand.co.uk"
    assert row["avg_suit_price_eur"] == 800

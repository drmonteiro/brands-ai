"""
Cross-city cache for brand-level attributes (HQ, prices, global stores, email).

Keyed by domain. City-specific fields (local store, city_presence) are never cached here.
"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from services.database import extract_domain
from services.postgres import PostgresManager

logger = logging.getLogger("services.brand_facts")

DEFAULT_TTL_DAYS = 30


def get_brand_facts_ttl_days() -> int:
    try:
        days = int(os.getenv("BRAND_FACTS_TTL_DAYS", str(DEFAULT_TTL_DAYS)))
        return max(1, days)
    except (TypeError, ValueError):
        return DEFAULT_TTL_DAYS


def _parse_ts(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    return None


def is_brand_facts_fresh(updated_at: Any, ttl_days: Optional[int] = None) -> bool:
    ts = _parse_ts(updated_at)
    if ts is None:
        return False
    ttl = ttl_days if ttl_days is not None else get_brand_facts_ttl_days()
    cutoff = datetime.now(timezone.utc) - timedelta(days=ttl)
    return ts >= cutoff


def _row_to_facts(row) -> Dict[str, Any]:
    data = dict(row)
    locs = data.get("store_locations")
    if isinstance(locs, str):
        try:
            locs = json.loads(locs)
        except Exception:
            locs = []
    data["store_locations"] = locs or []
    return data


async def get_brand_facts_batch(domains: List[str]) -> Dict[str, Dict[str, Any]]:
    """Load brand_facts for domains (includes stale rows; caller checks freshness)."""
    unique = [d for d in {extract_domain(d) for d in domains if d} if d]
    if not unique:
        return {}

    pool = await PostgresManager.get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT *
            FROM brand_facts
            WHERE domain = ANY($1::text[])
            """,
            unique,
        )
    return {row["domain"]: _row_to_facts(row) for row in rows}


def apply_brand_facts_to_brand(brand: Dict[str, Any], facts: Dict[str, Any]) -> None:
    """Merge cached brand-level fields; marks cache hit for enrich fast path."""
    if facts.get("name"):
        brand["name"] = facts["name"]
        brand["brand_name"] = facts["name"]
    if facts.get("website_url"):
        brand["website_url"] = facts["website_url"]
        brand["url"] = facts["website_url"]

    for key in (
        "origin_country",
        "headquarters_city",
        "headquarters_confidence",
        "contact_email",
        "avg_suit_price_eur",
        "price_range_min_eur",
        "price_range_max_eur",
        "price_note",
        "wool_percentage",
        "made_to_measure",
        "brand_style",
        "business_model",
        "company_overview",
    ):
        val = facts.get(key)
        if val is not None:
            brand[key] = val

    brand["store_count"] = int(facts.get("store_count") or 0)
    brand["store_count_confidence"] = facts.get("store_count_confidence") or "unknown"
    brand["store_locations"] = facts.get("store_locations") or []

    conf = (facts.get("store_count_confidence") or "unknown").lower()
    brand["_site_store_confidence"] = conf
    brand["_site_store_count"] = facts.get("store_count")
    brand["_site_store_addresses"] = list(facts.get("store_locations") or [])

    brand["_brand_facts_cache_hit"] = True
    brand["_brand_facts_domain"] = facts.get("domain")


def brand_dict_to_facts_row(brand: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract persistable brand-level facts from an enriched brand dict."""
    url = brand.get("website_url") or brand.get("url", "")
    domain = extract_domain(url)
    if not domain:
        return None

    store_locs = brand.get("store_locations") or []
    if isinstance(store_locs, str):
        try:
            store_locs = json.loads(store_locs)
        except Exception:
            store_locs = []

    return {
        "domain": domain,
        "name": brand.get("name") or brand.get("brand_name"),
        "website_url": url,
        "origin_country": brand.get("origin_country"),
        "headquarters_city": brand.get("headquarters_city"),
        "headquarters_confidence": brand.get("headquarters_confidence") or "unknown",
        "contact_email": brand.get("contact_email"),
        "avg_suit_price_eur": brand.get("avg_suit_price_eur"),
        "price_range_min_eur": brand.get("price_range_min_eur"),
        "price_range_max_eur": brand.get("price_range_max_eur"),
        "price_note": brand.get("price_note"),
        "store_count": brand.get("store_count"),
        "store_count_confidence": brand.get("store_count_confidence") or "unknown",
        "store_locations": store_locs,
        "wool_percentage": brand.get("wool_percentage"),
        "made_to_measure": brand.get("made_to_measure"),
        "brand_style": brand.get("brand_style"),
        "business_model": brand.get("business_model"),
        "company_overview": brand.get("company_overview") or brand.get("detailed_description"),
    }


async def upsert_brand_facts_from_brands(brands: List[Dict[str, Any]]) -> int:
    """Persist brand-level facts after full enrichment. Returns rows upserted."""
    rows = []
    for brand in brands:
        if brand.get("_brand_facts_cache_hit"):
            continue
        row = brand_dict_to_facts_row(brand)
        if row:
            rows.append(row)
    if not rows:
        return 0

    pool = await PostgresManager.get_pool()
    async with pool.acquire() as conn:
        for row in rows:
            await conn.execute(
                """
                INSERT INTO brand_facts (
                    domain, name, website_url, origin_country,
                    headquarters_city, headquarters_confidence,
                    contact_email,
                    avg_suit_price_eur, price_range_min_eur, price_range_max_eur, price_note,
                    store_count, store_count_confidence, store_locations,
                    wool_percentage, made_to_measure,
                    brand_style, business_model, company_overview,
                    updated_at
                ) VALUES (
                    $1, $2, $3, $4,
                    $5, $6,
                    $7,
                    $8, $9, $10, $11,
                    $12, $13, $14::jsonb,
                    $15, $16,
                    $17, $18, $19,
                    CURRENT_TIMESTAMP
                )
                ON CONFLICT (domain) DO UPDATE SET
                    name = EXCLUDED.name,
                    website_url = EXCLUDED.website_url,
                    origin_country = EXCLUDED.origin_country,
                    headquarters_city = EXCLUDED.headquarters_city,
                    headquarters_confidence = EXCLUDED.headquarters_confidence,
                    contact_email = EXCLUDED.contact_email,
                    avg_suit_price_eur = EXCLUDED.avg_suit_price_eur,
                    price_range_min_eur = EXCLUDED.price_range_min_eur,
                    price_range_max_eur = EXCLUDED.price_range_max_eur,
                    price_note = EXCLUDED.price_note,
                    store_count = EXCLUDED.store_count,
                    store_count_confidence = EXCLUDED.store_count_confidence,
                    store_locations = EXCLUDED.store_locations,
                    wool_percentage = EXCLUDED.wool_percentage,
                    made_to_measure = EXCLUDED.made_to_measure,
                    brand_style = EXCLUDED.brand_style,
                    business_model = EXCLUDED.business_model,
                    company_overview = EXCLUDED.company_overview,
                    updated_at = CURRENT_TIMESTAMP
                """,
                row["domain"],
                row["name"],
                row["website_url"],
                row["origin_country"],
                row["headquarters_city"],
                row["headquarters_confidence"],
                row["contact_email"],
                row["avg_suit_price_eur"],
                row["price_range_min_eur"],
                row["price_range_max_eur"],
                row["price_note"],
                row["store_count"],
                row["store_count_confidence"],
                json.dumps(row["store_locations"]),
                row["wool_percentage"],
                row["made_to_measure"],
                row["brand_style"],
                row["business_model"],
                row["company_overview"],
            )
    logger.info("[brand_facts] Upserted %d domain(s)", len(rows))
    return len(rows)

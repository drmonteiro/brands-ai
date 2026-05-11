"""
Field Merger for Confeções Lança Prospector

Merges brand data from three sources into a BrandLead object.
Extracted from validator.py Phase 3.

TRUST HIERARCHY (source priority per field):

  Field              | Priority 1       | Priority 2     | Priority 3
  -------------------|------------------|----------------|------------
  Address/phone      | Google Places    | LLM            | —
  Store count        | Google Places    | LLM            | —
  Store locations    | Google Places    | LLM            | —
  HQ address         | LLM             | Google Places   | —
  Prices             | Regex extraction | LLM from text  | —
  Wool/fabric        | LLM from scrape  | null           | —
  MTM/bespoke        | LLM from About   | Keyword scoring | —
  Founder/emails     | Scraping ONLY    | never LLM      | —
  Fit score          | LLM only         | —              | —
  city_presence_type | Google Places +  | LLM cross-check | —
  Contact email      | LLM             | Scraping        | —
  LinkedIn           | Scraping ONLY    | —              | —
"""
import logging
from typing import Dict, Any, Optional

from pydantic import ValidationError

from models import BrandLead, ExtractedContent
from data.premium_locations import detect_premium_location, calculate_location_score

logger = logging.getLogger("services.field_merger")

# Fields that may be JSON null from deep-analysis LLM (Task 5)
_LLM_NULLABLE_KEYS = (
    "madeToMeasure",
    "bespokeOnly",
    "appointmentOnly",
    "pricesVisible",
    "isChain",
    "woolPercentage",
    "contactName",
    "contactEmail",
    "contactPhone",
    "headquartersAddress",
)


def _snapshot_llm_for_merge(llm_data: Dict[str, Any]) -> Dict[str, Any]:
    return {k: llm_data.get(k) for k in _LLM_NULLABLE_KEYS}


def merge_brand_data(
    llm_data: Dict[str, Any],
    places_data: Dict[str, Any],
    scraped_data: Dict[str, Any],
    content_obj: Optional[ExtractedContent],
    target_city: str,
) -> BrandLead:
    """
    Merge data from LLM deep analysis, Google Places, and scraping
    into a single BrandLead object with source traceability.
    """
    url = llm_data.get("url", "")
    content_text = content_obj.content if content_obj else ""

    snapshot = _snapshot_llm_for_merge(llm_data)
    logger.info(
        "merge_brand_data pre-merge url=%s city=%s llm_nullable_snapshot=%s",
        url,
        target_city,
        snapshot,
    )

    # Premium Street Detection
    street, tier = detect_premium_location(content_text, target_city)
    location_quality = (
        "premium" if street else llm_data.get("locationQuality", "standard")
    )
    location_score = calculate_location_score(street, tier) if street else 0

    contact_email = llm_data.get("contactEmail") or scraped_data.get("contact_email")
    email_source = "llm" if llm_data.get("contactEmail") else (
        "scraping" if scraped_data.get("contact_email") else "none"
    )

    contact_linkedin = scraped_data.get("contact_linkedin")
    owner_name = scraped_data.get("owner_name")
    owner_role = scraped_data.get("owner_role")
    email_priority = scraped_data.get("email_priority")
    email_category = scraped_data.get("email_category")
    product_images = scraped_data.get("product_images", [])

    contact_name = llm_data.get("contactName") or owner_name
    contact_name_source = "llm" if llm_data.get("contactName") else (
        "scraping" if owner_name else "none"
    )
    contact_role_val = llm_data.get("contactRole") or owner_role

    contact_phone = llm_data.get("contactPhone") or places_data.get("places_phone")
    phone_source = "llm" if llm_data.get("contactPhone") else (
        "google_places" if places_data.get("places_phone") else "none"
    )

    places_store_count = places_data.get("places_store_count", 0)
    llm_store_count = llm_data.get("storeCount", 1) or 1
    final_store_count = places_store_count if places_store_count > 0 else llm_store_count
    store_count_source = "google_places" if places_store_count > 0 else "llm"

    places_locations = places_data.get("places_locations", [])
    llm_locations = llm_data.get("storeLocations", []) or []
    final_locations = places_locations if places_locations else llm_locations
    locations_source = "google_places" if places_locations else "llm"

    hq_address = llm_data.get("headquartersAddress") or places_data.get("places_address")
    hq_source = "llm" if llm_data.get("headquartersAddress") else (
        "google_places" if places_data.get("places_address") else "none"
    )

    if hq_address is None and not places_data.get("places_address"):
        logger.warning(
            "merge_brand_data: no HQ address from LLM or Places url=%s",
            url,
        )

    city_presence_type = llm_data.get("city_presence_type", "unknown")

    sources: Dict[str, str] = {
        "contact_email_source": email_source,
        "contact_name_source": contact_name_source,
        "contact_phone_source": phone_source,
        "store_count_source": store_count_source,
        "store_locations_source": locations_source,
        "headquarters_address_source": hq_source,
        "city_presence_type": city_presence_type,
        "made_to_measure": "llm"
        if "madeToMeasure" in llm_data
        else "absent",
        "wool_percentage": "llm"
        if "woolPercentage" in llm_data
        else "absent",
    }
    logger.debug("merge_brand_data field_sources=%s", sources)

    payload = dict(
        name=llm_data.get("name", "Unknown"),
        website_url=url,
        store_count=final_store_count,
        average_suit_price_usd=(
            llm_data.get("avgPrice") if llm_data.get("avgPrice") is not None else 0
        ),
        city=target_city,
        origin_country=llm_data.get("country", "International"),
        verified=llm_data.get("priceSource") == "found",
        brand_style=llm_data.get("brandStyle", "Premium"),
        business_model=llm_data.get("businessModel", "Retail"),
        company_overview=llm_data.get("whySelected", ""),
        detailed_description=llm_data.get("detailedDescription"),
        store_locations=final_locations,
        location_quality=location_quality,
        location_score=location_score,
        fit_score=llm_data.get("fitScore") if llm_data.get("fitScore") is not None else 0,
        wool_percentage=llm_data.get("woolPercentage"),
        made_to_measure=llm_data.get("madeToMeasure"),
        bespoke_only=llm_data.get("bespokeOnly"),
        appointment_only=llm_data.get("appointmentOnly"),
        prices_visible=llm_data.get("pricesVisible"),
        is_chain=llm_data.get("isChain"),
        contact_name=contact_name,
        contact_role=contact_role_val,
        contact_email=contact_email,
        contact_phone=contact_phone,
        contact_linkedin=contact_linkedin,
        owner_name=owner_name,
        owner_role=owner_role,
        email_priority=email_priority,
        email_category=email_category,
        headquarters_address=hq_address,
        city_presence_type=city_presence_type,
        passes_constraints=True,
        quality_score=getattr(content_obj, "quality_score", 0) if content_obj else 0,
        query_origin=getattr(content_obj, "query_origin", "Unknown") if content_obj else "Unknown",
        price_source=llm_data.get("priceSource") or scraped_data.get("price_source"),
        product_images=product_images,
    )

    try:
        brand = BrandLead(**payload)
    except ValidationError as e:
        logger.error(
            "merge_brand_data BrandLead validation failed url=%s errors=%s payload_keys=%s",
            url,
            e.errors(),
            list(payload.keys()),
        )
        raise

    brand._field_sources = sources

    return brand

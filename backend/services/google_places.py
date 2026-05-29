"""
Google Places API (New) integration for structured location data.
Uses Text Search to find boutique locations: store count, addresses, phone numbers.
"""

import asyncio
import logging
import os
from typing import Dict, Any, List, Optional
import httpx

from services.location_enrichment import _brand_name_matches

logger = logging.getLogger(__name__)

PLACES_API_BASE = "https://places.googleapis.com/v1/places:searchText"


def _get_api_key() -> Optional[str]:
    return os.getenv("GOOGLE_PLACES_API_KEY")


async def search_local_presence(
    brand_name: str,
    city: str,
    country: str = "",
) -> Optional[Dict[str, Any]]:
    """
    Search Google Places for a brand's local presence in a specific city.
    Returns structured data: address, phone, location, rating, etc.
    This is NOT headquarters — it is the local store/showroom in the target city.
    """
    api_key = _get_api_key()
    if not api_key:
        logger.warning("[PLACES] No GOOGLE_PLACES_API_KEY set — skipping")
        return None

    query = f"{brand_name} menswear {city}"
    if country:
        query += f" {country}"

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": (
            "places.displayName,"
            "places.formattedAddress,"
            "places.nationalPhoneNumber,"
            "places.internationalPhoneNumber,"
            "places.websiteUri,"
            "places.googleMapsUri,"
            "places.rating,"
            "places.userRatingCount,"
            "places.types,"
            "places.location,"
            "places.businessStatus"
        ),
    }

    body = {
        "textQuery": query,
        "maxResultCount": 3,
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(PLACES_API_BASE, json=body, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        places = data.get("places", [])
        if not places:
            logger.info("[PLACES] No local results for '%s'", query)
            return None

        place = places[0]
        place_name = place.get("displayName", {}).get("text", "")
        if not _brand_name_matches(place_name, brand_name):
            logger.info(
                "[PLACES] Name mismatch for '%s': got '%s'",
                brand_name, place_name,
            )
            return None

        result = {
            "name": place_name,
            "local_address": place.get("formattedAddress", ""),
            "local_phone": place.get("internationalPhoneNumber") or place.get("nationalPhoneNumber"),
            "website": place.get("websiteUri"),
            "maps_url": place.get("googleMapsUri"),
            "rating": place.get("rating"),
            "review_count": place.get("userRatingCount"),
            "types": place.get("types", []),
            "business_status": place.get("businessStatus"),
            "lat": place.get("location", {}).get("latitude"),
            "lng": place.get("location", {}).get("longitude"),
        }

        logger.info(
            "[PLACES] Local presence: %s @ %s (rating=%.1f, reviews=%d)",
            result["name"],
            result["local_address"],
            result.get("rating") or 0,
            result.get("review_count") or 0,
        )
        return result

    except httpx.HTTPStatusError as e:
        logger.error("[PLACES] HTTP error for '%s': %s", query, e)
        return None
    except Exception as e:
        logger.error("[PLACES] Error for '%s': %s", query, e)
        return None


# Backward compatibility alias
search_place = search_local_presence


async def count_brand_locations(
    brand_name: str,
    country: str = "",
    website_url: str = "",
) -> List[Dict[str, Any]]:
    """
    Search for ALL locations of a brand (not limited to one city).
    Returns list of places with addresses.
    """
    api_key = _get_api_key()
    if not api_key:
        return []

    query = f"{brand_name} store"
    if country:
        query += f" {country}"

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": (
            "places.displayName,"
            "places.formattedAddress,"
            "places.businessStatus,"
            "places.location,"
            "places.websiteUri"
        ),
    }

    body = {
        "textQuery": query,
        "maxResultCount": 20,
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(PLACES_API_BASE, json=body, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        places = data.get("places", [])
        results = []
        for p in places:
            status = p.get("businessStatus", "")
            if status == "CLOSED_PERMANENTLY":
                continue
            place_name = p.get("displayName", {}).get("text", "")
            if not _brand_name_matches(place_name, brand_name):
                continue
            results.append({
                "name": place_name,
                "address": p.get("formattedAddress", ""),
                "lat": p.get("location", {}).get("latitude"),
                "lng": p.get("location", {}).get("longitude"),
                "website": p.get("websiteUri"),
            })

        logger.info("[PLACES] Brand '%s': %d matched locations found", brand_name, len(results))
        return results

    except Exception as e:
        logger.error("[PLACES] Location count error for '%s': %s", brand_name, e)
        return []


async def enrich_with_places(
    brand_name: str,
    city: str,
    country: str = "",
    website_url: str = "",
    *,
    count_all_locations: bool = True,
) -> Dict[str, Any]:
    """
    Full enrichment: local presence in target city (always) + optional global store count.

    Call B (count_brand_locations) runs only when count_all_locations=True — e.g. when
    the brand's site store-locator did not yield verified store data.
    """
    primary = await search_local_presence(brand_name, city, country)
    locations: List[Dict[str, Any]] = []
    if count_all_locations:
        locations = await count_brand_locations(brand_name, country, website_url)
    else:
        logger.info(
            "[PLACES] Skipping global location count for '%s' (site store data verified)",
            brand_name,
        )

    result = {
        "local_store_address": None,
        "local_store_phone": None,
        "places_rating": None,
        "places_review_count": None,
        "places_maps_url": None,
        "places_store_count": 0,
        "places_locations": [],
        "places_website": None,
        # Deprecated — kept for backward compat in tests; do NOT use as HQ
        "places_address": None,
        "places_phone": None,
    }

    if primary:
        result["local_store_address"] = primary.get("local_address")
        result["local_store_phone"] = primary.get("local_phone")
        result["places_rating"] = primary.get("rating")
        result["places_review_count"] = primary.get("review_count")
        result["places_maps_url"] = primary.get("maps_url")
        result["places_website"] = primary.get("website")
        result["places_address"] = primary.get("local_address")
        result["places_phone"] = primary.get("local_phone")

    if locations:
        result["places_store_count"] = len(locations)
        result["places_locations"] = [loc["address"] for loc in locations if loc.get("address")]

    return result


async def batch_enrich_with_places(
    candidates: List[Dict[str, str]],
    max_concurrent: int = 5,
) -> List[Dict[str, Any]]:
    """
    Enrich multiple candidates with Google Places data in parallel.
    Each candidate dict needs: brand_name, city, country (optional), website_url (optional).
    Optional: count_all_locations (default True).
    """
    sem = asyncio.Semaphore(max_concurrent)

    async def enrich_one(candidate):
        async with sem:
            return await enrich_with_places(
                brand_name=candidate["brand_name"],
                city=candidate["city"],
                country=candidate.get("country", ""),
                website_url=candidate.get("website_url", ""),
                count_all_locations=candidate.get("count_all_locations", True),
            )

    results = await asyncio.gather(*(enrich_one(c) for c in candidates))
    return list(results)

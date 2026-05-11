"""
Google Places API (New) integration for structured location data.
Uses Text Search to find boutique locations: store count, addresses, phone numbers.
"""

import asyncio
import logging
import os
from typing import Dict, Any, List, Optional
import httpx

logger = logging.getLogger(__name__)

PLACES_API_BASE = "https://places.googleapis.com/v1/places:searchText"


def _get_api_key() -> Optional[str]:
    return os.getenv("GOOGLE_PLACES_API_KEY")


async def search_place(
    brand_name: str,
    city: str,
    country: str = "",
) -> Optional[Dict[str, Any]]:
    """
    Search Google Places for a brand in a specific city.
    Returns structured data: address, phone, location, rating, etc.
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
            logger.info("[PLACES] No results for '%s'", query)
            return None

        place = places[0]
        result = {
            "name": place.get("displayName", {}).get("text", ""),
            "address": place.get("formattedAddress", ""),
            "phone": place.get("internationalPhoneNumber") or place.get("nationalPhoneNumber"),
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
            "[PLACES] Found: %s @ %s (rating=%.1f, reviews=%d)",
            result["name"],
            result["address"],
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


async def count_brand_locations(
    brand_name: str,
    country: str = "",
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
            "places.location"
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
            results.append({
                "name": p.get("displayName", {}).get("text", ""),
                "address": p.get("formattedAddress", ""),
                "lat": p.get("location", {}).get("latitude"),
                "lng": p.get("location", {}).get("longitude"),
            })

        logger.info("[PLACES] Brand '%s': %d locations found", brand_name, len(results))
        return results

    except Exception as e:
        logger.error("[PLACES] Location count error for '%s': %s", brand_name, e)
        return []


async def enrich_with_places(
    brand_name: str,
    city: str,
    country: str = "",
    website_url: str = "",
) -> Dict[str, Any]:
    """
    Full enrichment: get primary place data + count all locations.
    Returns consolidated dict ready to merge into prospect data.
    """
    primary, locations = await asyncio.gather(
        search_place(brand_name, city, country),
        count_brand_locations(brand_name, country),
    )

    result = {
        "places_address": None,
        "places_phone": None,
        "places_rating": None,
        "places_review_count": None,
        "places_maps_url": None,
        "places_store_count": 0,
        "places_locations": [],
        "places_website": None,
    }

    if primary:
        result["places_address"] = primary.get("address")
        result["places_phone"] = primary.get("phone")
        result["places_rating"] = primary.get("rating")
        result["places_review_count"] = primary.get("review_count")
        result["places_maps_url"] = primary.get("maps_url")
        result["places_website"] = primary.get("website")

    if locations:
        # Filter to only locations whose name closely matches the brand
        brand_lower = brand_name.lower()
        matched = [
            loc for loc in locations
            if brand_lower in loc["name"].lower() or loc["name"].lower() in brand_lower
        ]
        result["places_store_count"] = len(matched) if matched else len(locations)
        result["places_locations"] = [loc["address"] for loc in (matched or locations)]

    return result


async def batch_enrich_with_places(
    candidates: List[Dict[str, str]],
    max_concurrent: int = 5,
) -> List[Dict[str, Any]]:
    """
    Enrich multiple candidates with Google Places data in parallel.
    Each candidate dict needs: brand_name, city, country (optional), website_url (optional).
    """
    sem = asyncio.Semaphore(max_concurrent)

    async def enrich_one(candidate):
        async with sem:
            return await enrich_with_places(
                brand_name=candidate["brand_name"],
                city=candidate["city"],
                country=candidate.get("country", ""),
                website_url=candidate.get("website_url", ""),
            )

    results = await asyncio.gather(*(enrich_one(c) for c in candidates))
    return list(results)

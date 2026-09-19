"""
Router for City Statistics
"""
import logging
from fastapi import APIRouter, HTTPException
from services.database import get_all_searched_cities, get_city_stats, get_prospects_by_city, delete_city_prospects

logger = logging.getLogger("router.cities")
router = APIRouter(prefix="/api/cities", tags=["cities"])

@router.get("")
async def list_cities():
    try:
        cities = await get_all_searched_cities()
        return {"cities": cities, "total": len(cities)}
    except Exception as e:
        logger.exception("Failed to list cities")
        raise HTTPException(status_code=503, detail="Database unavailable") from e

@router.get("/{city}/stats")
async def city_statistics(city: str):
    return {
        "stats": await get_city_stats(city),
        "top_prospects": await get_prospects_by_city(city, limit=5)
    }

@router.delete("/{city}")
async def delete_city(city: str):
    success = await delete_city_prospects(city)
    return {"success": True, "message": f"City {city} and its prospects were deleted."}

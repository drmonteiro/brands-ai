"""
Router for City Statistics
"""
from fastapi import APIRouter
from services.database import get_all_searched_cities, get_city_stats, get_prospects_by_city

router = APIRouter(prefix="/api/cities", tags=["cities"])

@router.get("")
async def list_cities():
    cities = await get_all_searched_cities()
    return {"cities": cities, "total": len(cities)}

@router.get("/{city}/stats")
async def city_statistics(city: str):
    return {
        "stats": await get_city_stats(city),
        "top_prospects": await get_prospects_by_city(city, limit=5)
    }

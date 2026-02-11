"""
Router for Analytics & Dashboards
"""
from fastapi import APIRouter
from services.database import get_dashboard_stats, get_price_analysis, get_prospects_filtered

router = APIRouter(prefix="/api", tags=["analytics"])

@router.get("/dashboard")
async def dashboard():
    return await get_dashboard_stats()

@router.get("/analytics/prices")
async def price_analytics():
    return await get_price_analysis()

@router.get("/analytics/stores")
async def store_analytics():
    total = await get_prospects_filtered()
    boutique = await get_prospects_filtered(max_stores=5)
    medium = await get_prospects_filtered(min_stores=6, max_stores=20)
    
    return {
        "total": total["total_count"],
        "by_size": {
            "boutique": boutique["total_count"],
            "medium": medium["total_count"]
        }
    }

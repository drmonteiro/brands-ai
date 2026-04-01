"""
Router for Prospect Management
"""
from typing import Optional, List, Dict
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from models import (
    ProspectFilters, ProspectStatus, SortField, SortOrder, 
    PriceRange, StoreSize
)
from services.database import (
    get_prospects_by_city,
    get_prospect_by_id,
    update_prospect_status,
    delete_prospect,
    get_prospects_filtered,
    get_filter_options,
    save_prospect_feedback,
)

router = APIRouter(prefix="/api/prospects", tags=["prospects"])

class StatusUpdateRequest(BaseModel):
    status: str
    notes: Optional[str] = None

class FeedbackRequest(BaseModel):
    feedback_type: str  # 'up' or 'down'
    comment: str
    manager_name: Optional[str] = "Comercial"

class SuppressionRequest(BaseModel):
    domain: str
    reason: Optional[str] = "Unsubscribed"

@router.post("/suppress")
async def suppress_brand(request: SuppressionRequest):
    from services.database import add_to_suppression_list
    await add_to_suppression_list(request.domain, request.reason)
    return {"success": True, "message": f"Domínio {request.domain} adicionado à lista de exclusão"}

@router.get("")
async def list_prospects(
    city: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    min_stores: Optional[int] = Query(None, ge=0),
    max_stores: Optional[int] = Query(None, ge=0),
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    min_score: Optional[float] = Query(None, ge=0, le=100),
    status: Optional[str] = Query(None),
    sort_by: str = Query("final_score"),
    sort_order: str = Query("desc"),
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    return await get_prospects_filtered(
        city=city, country=country, min_stores=min_stores, max_stores=max_stores,
        min_price=min_price, max_price=max_price, min_score=min_score,
        status=status, sort_by=sort_by, sort_order=sort_order,
        limit=limit, offset=offset
    )

@router.post("/filter")
async def filter_prospects_post(filters: ProspectFilters):
    # Enum conversion and preset logic from main.py
    status = filters.status.value if filters.status else None
    
    return await get_prospects_filtered(
        city=filters.city, min_stores=filters.min_stores, max_stores=filters.max_stores,
        min_price=filters.min_price, max_price=filters.max_price, 
        min_score=filters.min_score, status=status,
        sort_by=filters.sort_by.value, sort_order=filters.sort_order.value,
        limit=filters.limit, offset=filters.offset
    )

@router.get("/filters/options")
async def get_filter_options_endpoint():
    options = await get_filter_options()
    options["presets"] = [
        {"name": "ideal_boutiques", "label": "🏆 Ideal Boutiques", "params": {"max_stores": 5, "min_score": 70}},
        {"name": "luxury_only", "label": "💎 Luxury Only", "params": {"min_price": 2000}},
    ]
    return options

@router.get("/{prospect_id}")
async def get_prospect(prospect_id: str):
    p = await get_prospect_by_id(prospect_id)
    if not p: raise HTTPException(status_code=404, detail="Prospect não encontrado")
    return p

@router.patch("/{prospect_id}/status")
async def update_status(prospect_id: str, request: StatusUpdateRequest):
    if request.status not in ["new", "contacted", "converted", "rejected"]:
        raise HTTPException(status_code=400, detail="Estado inválido")
    if not await update_prospect_status(prospect_id, request.status, request.notes):
        raise HTTPException(status_code=404, detail="Prospect não encontrado")
    return {"success": True, "new_status": request.status}

@router.delete("/{prospect_id}")
async def remove_prospect(prospect_id: str):
    if not await delete_prospect(prospect_id):
        raise HTTPException(status_code=404, detail="Prospect não encontrado")
    return {"success": True}

@router.post("/{prospect_id}/feedback")
async def post_feedback(prospect_id: str, request: FeedbackRequest):
    if request.feedback_type not in ["up", "down"]:
        raise HTTPException(status_code=400, detail="Tipo de feedback inválido. Use 'up' ou 'down'.")
    
    if not request.comment or len(request.comment.strip()) < 3:
        raise HTTPException(status_code=400, detail="O comentário é obrigatório e deve ter pelo menos 3 caracteres.")

    result = await save_prospect_feedback(
        prospect_id, 
        request.feedback_type, 
        request.comment, 
        request.manager_name
    )
    return {"success": True, "data": result}

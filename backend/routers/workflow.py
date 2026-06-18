"""
Router for Prospecting Workflow (background jobs + status polling)
"""
import logging
from fastapi import APIRouter, HTTPException, Query
from models import SearchRequest
from services.prospect_jobs import get_prospect_job_status, start_prospect_job

logger = logging.getLogger("router.workflow")
router = APIRouter(prefix="/api/prospect", tags=["workflow"])


@router.post("")
async def start_prospect(request: SearchRequest):
    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    logger.info("NEW PROSPECT REQUEST: city=%s force_refresh=%s", request.city, request.force_refresh)
    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    try:
        return await start_prospect_job(request.city, request.force_refresh)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/status")
async def prospect_status(city: str = Query(..., min_length=1)):
    try:
        return await get_prospect_job_status(city)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

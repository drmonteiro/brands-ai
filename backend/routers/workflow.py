"""
Router for Prospecting Workflow (SSE)
"""
import logging
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from models import SearchRequest
from services.workflow_service import prospect_event_generator

logger = logging.getLogger("router.workflow")
router = APIRouter(prefix="/api/prospect", tags=["workflow"])


@router.post("")
async def start_prospect(request: SearchRequest):
    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    logger.info("NEW PROSPECT REQUEST: city=%s force_refresh=%s", request.city, request.force_refresh)
    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    return StreamingResponse(
        prospect_event_generator(request.city, request.force_refresh),
        media_type="text/event-stream",
    )

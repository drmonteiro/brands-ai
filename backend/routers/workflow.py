"""
Router for Prospecting Workflow (SSE)
"""
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from models import SearchRequest, WorkflowResumeRequest
from services.workflow_service import prospect_event_generator, resume_workflow_generator

router = APIRouter(prefix="/api/prospect", tags=["workflow"])

@router.post("")
async def start_prospect(request: SearchRequest):
    return StreamingResponse(
        prospect_event_generator(request.city, request.force_refresh), 
        media_type="text/event-stream"
    )

@router.post("/resume")
async def resume_prospect(request: WorkflowResumeRequest):
    return StreamingResponse(
        resume_workflow_generator(request.thread_id, request.node, request.data or {}), 
        media_type="text/event-stream"
    )

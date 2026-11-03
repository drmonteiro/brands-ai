"""
Router for LinkedIn outreach drafts. Assisted send only: this returns text and
links for a salesperson; nothing is sent to LinkedIn from here.
"""
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from models import BrandLead
from services.linkedin_contacts import build_people_search_url, normalize_profile_url
from services.linkedin_outreach import generate_linkedin_drafts

router = APIRouter(prefix="/api/linkedin", tags=["linkedin"])


class LinkedInDraftRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    brand_data: Dict[str, Any] = Field(alias="brandData")
    contact: Optional[Dict[str, Any]] = None


@router.post("/draft")
async def create_draft(request: LinkedInDraftRequest):
    try:
        brand = BrandLead.model_validate(request.brand_data)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=f"Erro de validação nos dados da marca: {e}")

    drafts = await generate_linkedin_drafts(brand, request.contact)
    profile_url = normalize_profile_url(
        (request.contact or {}).get("linkedin_url") or brand.contact_linkedin
    )
    return {
        **drafts,
        "profile_url": profile_url,
        "search_url": build_people_search_url(brand.name, brand.city),
    }

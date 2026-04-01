"""
Router for Email Operations
"""
from datetime import datetime
from fastapi import APIRouter, HTTPException
from models import ApprovalRequest
from services.email_service import send_partnership_email

router = APIRouter(prefix="/api/email", tags=["email"])

@router.post("/send")
async def send_email(request: ApprovalRequest):
    if not request.brand_name or not request.brand_data:
        raise HTTPException(status_code=400, detail="Dados incompletos")
    
    # [V3] Validate or convert dict to BrandLead to ensure AI draft generation has all fields
    from models import BrandLead
    try:
        brand_lead = BrandLead.model_validate(request.brand_data)
    except Exception as e:
        print(f"[EMAIL] ❌ Brand data validation failed: {e}")
        # If validation fails, we can still try to proceed with raw dict if send_partnership_email supports it,
        # but better to fail early with a clear message.
        raise HTTPException(status_code=422, detail=f"Erro de validação nos dados da marca: {str(e)}")

    result = await send_partnership_email(brand_lead)
    if result["success"]:
        # [V3] Auto-update status to contacted
        from services.database import update_prospect_status
        prospect_id = brand_lead.id
        if prospect_id:
            await update_prospect_status(
                prospect_id, 
                "contacted", 
                f"Proposta gerada por IA enviada em {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            )
        return {"success": True, "message": f"Email enviado para {request.brand_name}"}
    else:
        raise HTTPException(status_code=500, detail="Falha ao enviar email")

@router.post("/draft")
async def generate_draft(request: ApprovalRequest):
    if not request.brand_data:
        raise HTTPException(status_code=400, detail="Dados incompletos")
    
    from models import BrandLead
    from services.email_service import generate_personalized_outreach
    try:
        brand_lead = BrandLead.model_validate(request.brand_data)
        draft = await generate_personalized_outreach(brand_lead)
        
        # [V2] Support for mailto preparation
        from urllib.parse import quote
        recipient = brand_lead.contact_email or "comercial@lanca.pt"
        subject = f"Partnership Proposal: Lança & {brand_lead.name}"
        
        return {
            "success": True, 
            "draft": draft,
            "mailto": f"mailto:{recipient}?subject={quote(subject)}&body={quote(draft)}"
        }
    except Exception as e:
        print(f"[EMAIL-DRAFT] ❌ Draft generation failed: {e}")
        raise HTTPException(status_code=422, detail=f"Erro ao gerar rascunho: {str(e)}")

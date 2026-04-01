"""
Router for Email Operations
"""
from datetime import datetime
from fastapi import APIRouter, HTTPException
from models import ApprovalRequest
from services.email_service import send_partnership_email

router = APIRouter(prefix="/api", tags=["email"])

@router.post("/approve-email")
async def approve_email(request: ApprovalRequest):
    if not request.brand_name or not request.brand_data:
        raise HTTPException(status_code=400, detail="Dados incompletos")
    
    result = await send_partnership_email(request.brand_data)
    if result["success"]:
        # [V3] Auto-update status to contacted
        from services.database import update_prospect_status
        prospect_id = request.brand_data.get("id")
        if prospect_id:
            await update_prospect_status(
                prospect_id, 
                "contacted", 
                f"Proposta gerada por IA enviada em {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            )
        return {"success": True, "message": f"Email enviado para {request.brand_name}"}
    else:
        raise HTTPException(status_code=500, detail="Falha ao enviar email")

"""
Router for Data Export
"""
import io
import csv
from typing import Optional
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from services.database import get_prospects_filtered
from services.currency import usd_to_eur

router = APIRouter(prefix="/api/export", tags=["export"])

@router.get("/csv")
async def export_prospects_csv(
    city: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
):
    # Fetch all matching prospects (high limit to export all)
    result = await get_prospects_filtered(
        city=city,
        status=status,
        limit=10000, 
        offset=0
    )
    
    prospects = result.get("prospects", [])

    # Create CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Headers
    writer.writerow([
        "Nome", "Website", "Cidade", "País", "Preço (EUR)", 
        "Score", "Nome Contacto", "Cargo", "Email Contacto", 
        "Telefone", "LinkedIn", "Status", "Lojas"
    ])
    
    for p in prospects:
        # Resolve legacy field names correctly
        price = p.get("avg_suit_price_eur") or p.get("avgSuitPriceEUR") or p.get("averageSuitPriceUSD")
        if p.get("averageSuitPriceUSD") and not p.get("avg_suit_price_eur"):
            price = round(usd_to_eur(float(p.get("averageSuitPriceUSD"))), 2)
            
        score = p.get("final_score") or p.get("fit_score") or p.get("fitScore") or 0
        
        writer.writerow([
            p.get("name", ""),
            p.get("website_url") or p.get("websiteUrl", ""),
            p.get("city", ""),
            p.get("country") or p.get("originCountry", ""),
            price if price else "",
            score,
            p.get("contact_name") or p.get("contactName", ""),
            p.get("contact_role") or p.get("contactRole", ""),
            p.get("contact_email") or p.get("contactEmail", ""),
            p.get("contact_phone") or p.get("contactPhone", ""),
            p.get("contact_linkedin") or p.get("contactLinkedin", ""),
            p.get("status", "new"),
            p.get("store_count") or p.get("storeCount", 0),
        ])

    output.seek(0)
    filename = f"lanca_prospects_{city if city else 'all'}.csv"
    
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )

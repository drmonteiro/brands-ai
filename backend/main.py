"""
FastAPI Backend for Confeções Lança Lead Generation
"""

import asyncio
import json
from datetime import datetime
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from models import SearchRequest, ApprovalRequest, BrandLead
from agents.prospector import run_prospector_workflow, create_initial_state
from services.email_service import send_partnership_email

# Create FastAPI app
app = FastAPI(
    title="Confeções Lança Lead Generation API",
    description="AI-powered prospecting for boutique menswear brands",
    version="1.0.0",
)

# Configure CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Confeções Lança Lead Generation API",
        "version": "1.0.0",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


async def prospect_event_generator(city: str) -> AsyncGenerator[str, None]:
    """
    Generator that yields SSE events during the prospecting workflow.
    """
    try:
        print(f"[API] Starting prospect search for: {city}")
        
        # Create initial state
        initial_state = create_initial_state(city)
        
        # Run the workflow
        result = await run_prospector_workflow(initial_state)
        
        print(f"[API] Workflow complete!")
        print(f"[API] verified_brands count: {len(result.verified_brands)}")
        print(f"[API] potential_brands count: {len(result.potential_brands)}")
        
        # Stream progress updates
        for progress_msg in result.progress:
            data = json.dumps({
                "type": "progress",
                "message": progress_msg,
                "timestamp": datetime.now().isoformat(),
            })
            yield f"data: {data}\n\n"
            await asyncio.sleep(0.05)  # Small delay for smoother streaming
        
        # Convert BrandLead objects to dicts for JSON serialization
        verified_brands_dict = [
            {
                "name": b.name,
                "websiteUrl": b.website_url,
                "storeCount": b.store_count,
                "averageSuitPriceUSD": b.average_suit_price_usd,
                "city": b.city,
                "originCountry": b.origin_country,
                "verified": b.verified,
                "revenue": b.revenue,
                "clothingTypes": b.clothing_types,
                "targetGender": b.target_gender,
                "brandStyle": b.brand_style,
                "businessModel": b.business_model,
                "companyOverview": b.company_overview,
                "verificationLog": b.verification_log,
                "passesConstraints": b.passes_constraints,
            }
            for b in result.verified_brands
        ]
        
        # Send final results
        print(f"[API] Sending {len(verified_brands_dict)} brands to frontend...")
        final_data = json.dumps({
            "type": "complete",
            "verifiedBrands": verified_brands_dict,
            "exchangeRate": result.exchange_rate,
            "priceThresholdUSD": result.price_threshold_usd,
            "timestamp": datetime.now().isoformat(),
        })
        print(f"[API] Final data size: {len(final_data)} chars")
        yield f"data: {final_data}\n\n"
        print(f"[API] ✅ Data sent successfully!")
        
    except Exception as error:
        print(f"[API] ❌ Error in prospect search: {error}")
        import traceback
        traceback.print_exc()
        error_data = json.dumps({
            "type": "error",
            "message": str(error),
        })
        yield f"data: {error_data}\n\n"


@app.post("/api/prospect")
async def prospect_brands(request: SearchRequest):
    """
    Start a prospecting search for boutique menswear brands.
    Returns Server-Sent Events stream with progress updates.
    """
    city = request.city.strip()
    
    if not city:
        raise HTTPException(status_code=400, detail="City parameter is required")
    
    return StreamingResponse(
        prospect_event_generator(city),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@app.post("/api/approve-email")
async def approve_email(request: ApprovalRequest):
    """
    Handle human approval for sending emails to specific brands.
    This is the human-in-the-loop trigger point.
    """
    if not request.brand_name or not request.brand_data:
        raise HTTPException(
            status_code=400,
            detail="Brand name and data are required"
        )
    
    print(f"[API] Approval received for: {request.brand_name}")
    
    # Send the email
    email_result = await send_partnership_email(request.brand_data)
    
    if email_result["success"]:
        return {
            "success": True,
            "message": f"Email sent successfully to {request.brand_name}",
            "timestamp": datetime.now().isoformat(),
        }
    else:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Failed to send email",
                "details": email_result.get("error"),
            }
        )


# Run with: uvicorn main:app --reload --port 8000
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

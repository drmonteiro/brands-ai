"""
Workflow Service
Manages SSE generators for prospecting workflows.
"""
import json
import asyncio
from datetime import datetime
from typing import Dict, AsyncGenerator
from models import BrandLead
from agents.nodes.initializer import create_initial_state
from agents.graph import run_prospector_workflow, _get_app_with_postgres
from services.database import city_has_results, get_prospects_by_city

async def prospect_event_generator(city: str, force_refresh: bool = False) -> AsyncGenerator[str, None]:
    """SSE generator for new prospecting search"""
    try:
        # 1. Cache handling
        if not force_refresh and await city_has_results(city):
            yield f"data: {json.dumps({'type': 'progress', 'message': f'📦 Usando cache para {city}'})}\n\n"
            cached_leads = await get_prospects_by_city(city, limit=50)
            # Convert to dicts for JSON serialization, handling pydantic models if they appear
            brands = []
            for b in cached_leads:
                if hasattr(b, "model_dump"):
                    brands.append(b.model_dump(by_alias=True))
                elif isinstance(b, dict):
                    # Ensure camelCase for frontend
                    material_comp = b.get("material_composition", [])
                    if isinstance(material_comp, str):
                        try:
                            material_comp = json.loads(material_comp)
                        except:
                            material_comp = []
                            
                    store_locs = b.get("store_locations", [])
                    if isinstance(store_locs, str):
                        try:
                            store_locs = json.loads(store_locs)
                        except:
                            store_locs = []
                            
                    brand_dict = {
                        "name": b.get("name"),
                        "websiteUrl": b.get("website_url"),
                        "storeCount": b.get("store_count"),
                        "averageSuitPriceUSD": (b.get("avg_suit_price_eur") or 0) * 1.08,
                        "city": b.get("city"),
                        "originCountry": b.get("country"),
                        "verified": b.get("status") != "new",
                        "brandStyle": b.get("brand_style"),
                        "businessModel": b.get("business_model"),
                        "companyOverview": b.get("company_overview"),
                        "detailedDescription": b.get("detailed_description"),
                        "storeLocations": store_locs,
                        "locationQuality": b.get("location_quality") or ("premium" if b.get("location_score", 0) > 0 else "standard"),
                        "locationScore": b.get("location_score", 0),
                        "fitScore": b.get("fit_score", 0),
                        "woolPercentage": material_comp[0] if material_comp else None,
                        "madeToMeasure": b.get("made_to_measure", False)
                    }
                    brands.append(brand_dict)
                else:
                    brands.append(b)

            yield f"data: {json.dumps({'type': 'complete', 'verifiedBrands': brands, 'cached': True})}\n\n"
            return

        # 2. Run Workflow (STREAMING)
        initial_state = create_initial_state(city).model_dump()
        initial_state["force_refresh"] = force_refresh
        
        # Unique thread_id for Refresh
        import time
        thread_id = f"prospect_search_{city}"
        if force_refresh:
            thread_id = f"prospect_search_{city}_{int(time.time())}"
            
        config = {"configurable": {"thread_id": thread_id}}
        
        last_yielded_progress_idx = 0
        final_result = {}

        async with _get_app_with_postgres() as app:
            async for event in app.astream(initial_state, config=config, stream_mode="values"):
                # Track latest state result
                final_result = event
                
                # Check for new progress messages to stream
                progress = event.get("progress", [])
                if len(progress) > last_yielded_progress_idx:
                    for i in range(last_yielded_progress_idx, len(progress)):
                        yield f"data: {json.dumps({'type': 'progress', 'message': progress[i]})}\n\n"
                        await asyncio.sleep(0.01)
                    last_yielded_progress_idx = len(progress)
            
            # 3. Finalization
            # Check if finalized or interrupted (HIL is currently disabled but good to keep logic)
            state = await app.aget_state(config)
            interrupted = len(state.next) > 0
            
            if interrupted:
                yield f"data: {json.dumps({'type': 'waiting_approval', 'next_node': state.next[0], 'thread_id': thread_id})}\n\n"
            else:
                raw_brands = final_result.get('verified_brands', [])
                brands = [b.model_dump(by_alias=True) if hasattr(b, 'model_dump') else b for b in raw_brands]
                yield f"data: {json.dumps({'type': 'complete', 'verifiedBrands': brands})}\n\n"
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        yield f"data: {json.dumps({'type': 'error', 'message': str(e) or 'Erro interno no servidor'})}\n\n"

async def resume_workflow_generator(thread_id: str, node: str, data: Dict) -> AsyncGenerator[str, None]:
    """SSE generator for resuming search"""
    config = {"configurable": {"thread_id": thread_id}}
    try:
        async with _get_app_with_postgres() as app:
            update_data = {}
            if node == "discovery":
                if data.get("queries"):
                    update_data["search_queries"] = data["queries"]
                update_data["queries_approved"] = True
            elif node == "persistence":
                if data.get("brands"):
                    update_data["potential_brands"] = data["brands"]
                update_data["brands_approved"] = True
            
            if update_data:
                await app.aupdate_state(config, update_data)

            async for _ in app.astream(None, config=config, stream_mode="values"): pass
                
            final_state = await app.aget_state(config)
            result = final_state.values
            next_node = final_state.next
            interrupted = len(next_node) > 0
            
            if interrupted:
                 yield f"data: {json.dumps({'type': 'waiting_approval', 'next_node': next_node[0], 'thread_id': thread_id, 'search_queries': result.get('search_queries')})}\n\n"
            else:
                 brands = [b.model_dump(by_alias=True) if hasattr(b, 'model_dump') else b for b in result.get('verified_brands', [])]
                 yield f"data: {json.dumps({'type': 'complete', 'verifiedBrands': brands})}\n\n"
    except Exception as e:
        import traceback
        traceback.print_exc()
        yield f"data: {json.dumps({'type': 'error', 'message': str(e) or 'Erro interno no servidor'})}\n\n"

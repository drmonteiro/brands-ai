"""
Workflow Service
Manages SSE generators for prospecting workflows.
Includes heartbeat mechanism to prevent Azure SSE timeout on large cities.
"""
import json
import asyncio
import time
from datetime import datetime
from typing import Dict, AsyncGenerator
from models import BrandLead
from agents.nodes.initializer import create_initial_state
from agents.graph import run_prospector_workflow, _get_app_with_postgres
from services.database import city_has_results, get_prospects_by_city

# Heartbeat interval in seconds — Azure Static Web Apps times out idle SSE after ~240s
# Send heartbeat every 25s to keep the connection alive
HEARTBEAT_INTERVAL = 25.0


async def prospect_event_generator(city: str, force_refresh: bool = False) -> AsyncGenerator[str, None]:
    """SSE generator for new prospecting search with heartbeat to prevent Azure timeout."""
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

        # 2. Run Workflow (STREAMING with heartbeat)
        initial_state = create_initial_state(city).model_dump()
        initial_state["force_refresh"] = force_refresh
        
        # Unique thread_id for Refresh
        thread_id = f"prospect_search_{city}"
        if force_refresh:
            thread_id = f"prospect_search_{city}_{int(time.time())}"
            
        config = {"configurable": {"thread_id": thread_id}}
        
        # Use a queue to decouple workflow execution from SSE streaming
        # This allows us to emit heartbeats while the workflow is busy
        queue: asyncio.Queue = asyncio.Queue()
        workflow_done = asyncio.Event()
        workflow_error: list = []
        
        async def run_workflow():
            """Run the workflow in a background task, pushing SSE events to the queue."""
            last_yielded_progress_idx = 0
            final_result = {}
            try:
                async with _get_app_with_postgres() as app:
                    async for event in app.astream(initial_state, config=config, stream_mode="values"):
                        # Track latest state result
                        final_result = event
                        
                        # Check for new progress messages to stream
                        progress = event.get("progress", [])
                        if len(progress) > last_yielded_progress_idx:
                            for i in range(last_yielded_progress_idx, len(progress)):
                                msg = f"data: {json.dumps({'type': 'progress', 'message': progress[i]})}\n\n"
                                await queue.put(msg)
                            last_yielded_progress_idx = len(progress)
                    
                    # Finalization
                    state = await app.aget_state(config)
                    interrupted = len(state.next) > 0
                    
                    if interrupted:
                        msg = f"data: {json.dumps({'type': 'waiting_approval', 'next_node': state.next[0], 'thread_id': thread_id})}\n\n"
                        await queue.put(msg)
                    else:
                        raw_brands = final_result.get('verified_brands', [])
                        brands = [b.model_dump(by_alias=True) if hasattr(b, 'model_dump') else b for b in raw_brands]
                        msg = f"data: {json.dumps({'type': 'complete', 'verifiedBrands': brands})}\n\n"
                        await queue.put(msg)
            except Exception as e:
                import traceback
                traceback.print_exc()
                error_msg = f"data: {json.dumps({'type': 'error', 'message': str(e) or 'Erro interno no servidor'})}\n\n"
                await queue.put(error_msg)
            finally:
                workflow_done.set()
        
        # Start the workflow in the background
        workflow_task = asyncio.create_task(run_workflow())
        
        # Stream events with heartbeat
        heartbeat_count = 0
        while not workflow_done.is_set() or not queue.empty():
            try:
                # Wait for next event or timeout for heartbeat
                item = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_INTERVAL)
                yield item
            except asyncio.TimeoutError:
                # No event in HEARTBEAT_INTERVAL seconds — send heartbeat to keep connection alive
                heartbeat_count += 1
                yield f"data: {json.dumps({'type': 'heartbeat', 'count': heartbeat_count, 'ts': int(time.time())})}\n\n"
        
        # Drain any remaining items in the queue
        while not queue.empty():
            item = await queue.get()
            yield item
        
        # Ensure the task is complete
        await workflow_task
            
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

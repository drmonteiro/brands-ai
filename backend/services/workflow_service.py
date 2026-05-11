"""
Workflow Service
Manages SSE generators for prospecting workflows.
Includes heartbeat mechanism to prevent Azure SSE timeout on large cities.
"""
import json
import asyncio
import time
import logging
from datetime import datetime
from typing import Dict, AsyncGenerator
from models import BrandLead
from agents.graph import _get_app_with_postgres
from agents.nodes.pipeline_timing import format_duration
from services.database import city_has_results, get_prospects_by_city

logger = logging.getLogger("workflow")

HEARTBEAT_INTERVAL = 25.0


def _create_initial_state(city: str) -> dict:
    """Create minimal initial state for the new simplified pipeline."""
    return {
        "target_city": city,
        "target_country": "",
        "exchange_rate": 1.08,
        "search_results_raw": [],
        "filtered_brands": [],
        "enriched_brands": [],
        "verified_brands": [],
        "progress": [],
        "error": None,
    }


async def prospect_event_generator(city: str, force_refresh: bool = False) -> AsyncGenerator[str, None]:
    """SSE generator for new prospecting search with heartbeat to prevent Azure timeout."""
    start_time = time.time()
    logger.info("Starting prospect pipeline for '%s' (force_refresh=%s)", city, force_refresh)
    try:
        # 1. Cache handling
        if not force_refresh and await city_has_results(city):
            logger.info("Cache HIT for '%s' — returning cached results", city)
            yield f"data: {json.dumps({'type': 'progress', 'message': f'📦 Usando cache para {city}'})}\n\n"
            cached_leads = await get_prospects_by_city(city, limit=50)
            brands = []
            for b in cached_leads:
                if hasattr(b, "model_dump"):
                    brands.append(b.model_dump(by_alias=True))
                elif isinstance(b, dict):
                    material_comp = b.get("material_composition", [])
                    if isinstance(material_comp, str):
                        try:
                            material_comp = json.loads(material_comp)
                        except Exception:
                            material_comp = []

                    store_locs = b.get("store_locations", [])
                    if isinstance(store_locs, str):
                        try:
                            store_locs = json.loads(store_locs)
                        except Exception:
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
                        "fitScore": b.get("fit_score", 0),
                        "woolPercentage": material_comp[0] if material_comp else None,
                        "madeToMeasure": b.get("made_to_measure") is True,
                        "headquartersAddress": b.get("headquarters_address"),
                    }
                    brands.append(brand_dict)
                else:
                    brands.append(b)

            logger.info("Returning %d cached brands for '%s' (%.1fs)", len(brands), city, time.time() - start_time)
            yield f"data: {json.dumps({'type': 'complete', 'verifiedBrands': brands, 'cached': True})}\n\n"
            return

        # 2. Run Workflow (STREAMING with heartbeat)
        logger.info("Cache MISS for '%s' — starting full pipeline", city)
        initial_state = _create_initial_state(city)

        thread_id = f"prospect_search_{city}"
        if force_refresh:
            thread_id = f"prospect_search_{city}_{int(time.time())}"

        config = {"configurable": {"thread_id": thread_id}}

        queue: asyncio.Queue = asyncio.Queue()
        workflow_done = asyncio.Event()

        async def run_workflow():
            last_yielded_progress_idx = 0
            final_result = {}
            try:
                logger.info("Compiling LangGraph app (thread=%s)", thread_id)
                async with _get_app_with_postgres() as app:
                    logger.info("Streaming graph execution for '%s'...", city)
                    async for event in app.astream(initial_state, config=config, stream_mode="values"):
                        final_result = event

                        progress = event.get("progress", [])
                        if len(progress) > last_yielded_progress_idx:
                            for i in range(last_yielded_progress_idx, len(progress)):
                                msg = f"data: {json.dumps({'type': 'progress', 'message': progress[i]})}\n\n"
                                await queue.put(msg)
                            last_yielded_progress_idx = len(progress)

                    raw_brands = final_result.get("verified_brands", [])
                    brands = [b.model_dump(by_alias=True) if hasattr(b, "model_dump") else b for b in raw_brands]
                    elapsed = time.time() - start_time
                    logger.info(
                        "[PIPELINE] COMPLETE | city=%s | brands=%d | duration=%s (%.2f min)",
                        city, len(brands), format_duration(elapsed), elapsed / 60.0,
                    )
                    msg = f"data: {json.dumps({'type': 'complete', 'verifiedBrands': brands})}\n\n"
                    await queue.put(msg)
            except Exception as e:
                logger.exception("Workflow error for '%s'", city)
                error_msg = f"data: {json.dumps({'type': 'error', 'message': str(e) or 'Erro interno no servidor'})}\n\n"
                await queue.put(error_msg)
            finally:
                workflow_done.set()

        workflow_task = asyncio.create_task(run_workflow())

        heartbeat_count = 0
        while not workflow_done.is_set() or not queue.empty():
            try:
                item = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_INTERVAL)
                yield item
            except asyncio.TimeoutError:
                heartbeat_count += 1
                yield f"data: {json.dumps({'type': 'heartbeat', 'count': heartbeat_count, 'ts': int(time.time())})}\n\n"

        while not queue.empty():
            item = await queue.get()
            yield item

        await workflow_task

    except Exception as e:
        logger.exception("Fatal error in prospect_event_generator for '%s'", city)
        yield f"data: {json.dumps({'type': 'error', 'message': str(e) or 'Erro interno no servidor'})}\n\n"

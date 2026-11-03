"""
Background prospect pipeline jobs.

Runs independently of HTTP/SSE connections so clients can navigate away
while discovery → filter → enrich → score_save completes and saves to DB.
"""
import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from agents.nodes.pipeline_timing import format_duration
from services.currency import get_eur_usd_rate
from services.database import city_has_results, get_active_leads_for_city, get_city_stats, normalize_city
from services.lead_recheck import recheck_city_leads

logger = logging.getLogger("prospect_jobs")

_lock = asyncio.Lock()
_jobs: Dict[str, "ProspectJob"] = {}


class JobStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


def _create_initial_state(city: str) -> dict:
    return {
        "target_city": city,
        "target_country": "",
        "exchange_rate": get_eur_usd_rate(),
        "search_results_raw": [],
        "filtered_brands": [],
        "enriched_brands": [],
        "verified_brands": [],
        "progress": [],
        "error": None,
    }


@dataclass
class ProspectJob:
    city: str
    force_refresh: bool
    regenerate: bool = False
    summary: Optional[Dict[str, int]] = None
    status: JobStatus = JobStatus.RUNNING
    progress: List[str] = field(default_factory=list)
    error: Optional[str] = None
    brand_count: int = 0
    similarity_degraded: bool = False
    similarity_failure_count: int = 0
    cached: bool = False
    started_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    task: Optional[asyncio.Task] = None

    def to_dict(self) -> dict:
        return {
            "city": self.city,
            "status": self.status.value,
            "progress": self.progress,
            "error": self.error,
            "brandCount": self.brand_count,
            "similarityDegraded": self.similarity_degraded,
            "similarityFailureCount": self.similarity_failure_count,
            "cached": self.cached,
            "summary": self.summary,
        }


async def _execute_pipeline(job: ProspectJob, keep_running: bool = False) -> None:
    # Lazy import — LangGraph/Exa/LangChain only load when a pipeline actually runs
    from agents.graph import _get_app_with_postgres

    city = job.city
    start_time = time.time()
    try:
        initial_state = _create_initial_state(city)
        thread_id = f"prospect_search_{city}"
        if job.force_refresh:
            thread_id = f"prospect_search_{city}_{int(time.time())}"
        config = {"configurable": {"thread_id": thread_id}}

        logger.info(
            "Background pipeline starting for '%s' (force_refresh=%s, thread=%s)",
            city, job.force_refresh, thread_id,
        )
        async with _get_app_with_postgres() as app:
            final_result = {}
            async for event in app.astream(initial_state, config=config, stream_mode="values"):
                final_result = event
                progress = event.get("progress", [])
                if len(progress) > len(job.progress):
                    job.progress = list(progress)

            raw_brands = final_result.get("verified_brands", [])
            job.brand_count = len(raw_brands)
            job.similarity_degraded = bool(final_result.get("similarity_degraded"))
            job.similarity_failure_count = int(final_result.get("similarity_failure_count") or 0)
            if not keep_running:
                job.status = JobStatus.COMPLETED
                job.completed_at = time.time()
            elapsed = time.time() - start_time
            logger.info(
                "[PIPELINE] COMPLETE | city=%s | brands=%d | duration=%s (%.2f min)",
                city, job.brand_count, format_duration(elapsed), elapsed / 60.0,
            )
    except Exception as e:
        logger.exception("Background pipeline failed for '%s'", city)
        job.status = JobStatus.FAILED
        job.error = str(e) or "Erro interno no servidor"
        job.completed_at = time.time()


async def _run_job(job: ProspectJob) -> None:
    """Regenerating cleans up old leads only after the search succeeded, so a failure changes nothing."""
    if not job.regenerate:
        await _execute_pipeline(job)
        return

    try:
        old_leads = await get_active_leads_for_city(job.city)
    except Exception as e:
        logger.exception("Could not read leads to regenerate '%s'", job.city)
        job.status = JobStatus.FAILED
        job.error = str(e) or "Erro interno no servidor"
        job.completed_at = time.time()
        return

    await _execute_pipeline(job, keep_running=True)
    if job.status != JobStatus.RUNNING:
        return

    try:
        job.progress = [*job.progress, f"🔁 A rever {len(old_leads)} marcas já guardadas…"]
        job.summary = await recheck_city_leads(job.city, old_leads)
        job.summary["added"] = job.brand_count
        job.status = JobStatus.COMPLETED
    except Exception as e:
        logger.exception("Regeneration failed for '%s'", job.city)
        job.status = JobStatus.FAILED
        job.error = str(e) or "Erro interno no servidor"
    job.completed_at = time.time()


async def _cached_response(city: str) -> dict:
    stats = await get_city_stats(city)
    count = int(stats.get("total_prospects") or 0)
    return {
        "city": city,
        "status": "completed",
        "cached": True,
        "brandCount": count,
        "progress": [f"📦 Usando cache para {city}"],
        "similarityDegraded": False,
        "similarityFailureCount": 0,
        "error": None,
    }


async def start_prospect_job(city: str, force_refresh: bool = False, regenerate: bool = False) -> dict:
    """Start a background pipeline or return cache / in-flight status."""
    city = city.strip()
    if not city:
        raise ValueError("City is required")

    key = normalize_city(city)

    async with _lock:
        existing = _jobs.get(key)
        if existing and existing.status == JobStatus.RUNNING:
            payload = existing.to_dict()
            payload["alreadyRunning"] = True
            return payload

        if not force_refresh and await city_has_results(city):
            return await _cached_response(city)

        job = ProspectJob(city=city, force_refresh=force_refresh, regenerate=regenerate)
        _jobs[key] = job
        job.task = asyncio.create_task(_run_job(job))
        logger.info("Queued background job for '%s'", city)
        return job.to_dict()


async def get_prospect_job_status(city: str) -> dict:
    """Poll job progress; falls back to DB cache or idle."""
    city = city.strip()
    if not city:
        raise ValueError("City is required")

    key = normalize_city(city)
    job = _jobs.get(key)
    if job:
        return job.to_dict()

    if await city_has_results(city):
        return await _cached_response(city)

    return {
        "city": city,
        "status": "idle",
        "progress": [],
        "brandCount": 0,
        "similarityDegraded": False,
        "similarityFailureCount": 0,
        "cached": False,
        "error": None,
    }

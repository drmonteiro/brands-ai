"""
Utility functions for LangGraph nodes.
"""
import asyncio
import json
import logging
from typing import Any, Optional
import re
from urllib.parse import urlparse
from langchain_core.rate_limiters import InMemoryRateLimiter
from langchain_openai import AzureChatOpenAI
from config import Config
from services.currency import get_eur_usd_rate, eur_to_usd as _eur_to_usd
from services.llm_tasks import task_uses_fast_model


# Without this, one stalled Azure call blocks the whole pipeline forever.
LLM_REQUEST_TIMEOUT_SEC = 180
LLM_MAX_RETRIES = 3
JSON_ATTEMPTS = 2

logger = logging.getLogger("node.utils")

# Shared by every model, so parallel steps can't overrun Azure's limits together.
_rate_limiter = InMemoryRateLimiter(requests_per_second=3, check_every_n_seconds=0.1, max_bucket_size=6)


def get_llm(fast: bool = False, temperature: float = 0.3) -> AzureChatOpenAI:
    """
    Get Azure OpenAI LLM instance.

    Args:
        fast: If True, use GPT-5-mini for quick tasks. If False, use GPT-5.1 for deep analysis.
        temperature: Sampling temperature (may be overridden for certain models).
    """
    deployment = Config.AZURE_OPENAI_DEPLOYMENT_FAST if fast else Config.AZURE_OPENAI_DEPLOYMENT

    # Newer Azure models require temperature=1.0 and fail if 0.0 is provided
    safe_temperature = 1.0 if "mini" in deployment or "gpt-5" in deployment else temperature

    return AzureChatOpenAI(
        azure_endpoint=Config.AZURE_OPENAI_ENDPOINT,
        api_key=Config.AZURE_OPENAI_API_KEY,
        api_version=Config.AZURE_OPENAI_API_VERSION,
        deployment_name=deployment,
        temperature=safe_temperature,
        max_tokens=12000,
        timeout=LLM_REQUEST_TIMEOUT_SEC,
        max_retries=LLM_MAX_RETRIES,
        rate_limiter=_rate_limiter,
    )


def get_llm_for_task(task: str, temperature: float = 0.3) -> AzureChatOpenAI:
    """
    Pipeline LLM picker. See services/llm_tasks.py for task keys and env overrides.
    """
    return get_llm(fast=task_uses_fast_model(task), temperature=temperature)


async def ainvoke_json(llm: Any, prompt: str) -> Any:
    """Call the LLM and parse its JSON, trying again if the answer isn't valid JSON."""
    for attempt in range(1, JSON_ATTEMPTS + 1):
        response = await llm.ainvoke(prompt)
        raw = response.content.replace("```json", "").replace("```", "").strip()
        try:
            return json.loads(raw)
        except ValueError as e:
            if attempt == JSON_ATTEMPTS:
                raise
            logger.warning("LLM returned invalid JSON, retrying: %s", e)
            await asyncio.sleep(1)


async def get_exchange_rate() -> float:
    """EUR→USD rate (EUR_USD_RATE env, default 1.08)."""
    return get_eur_usd_rate()


def convert_eur_to_usd(eur: float, rate: Optional[float] = None) -> float:
    return _eur_to_usd(eur, rate)


def normalize_url(url: str) -> str:
    """Normalize URL for comparison to detect duplicates."""
    if not url:
        return ""
    try:
        normalized = url.lower().strip()
        normalized = re.sub(r'^https?://', '', normalized)
        normalized = re.sub(r'^www\.', '', normalized)
        normalized = normalized.rstrip('/')
        normalized = normalized.split('?')[0].split('#')[0]
        return normalized
    except Exception:
        return url.lower().strip()


def get_domain_from_url(url: str) -> str:
    """Extract base domain from URL."""
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return url

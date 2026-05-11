"""
Utility functions for LangGraph nodes.
"""
from typing import Optional
import re
from urllib.parse import urlparse
from langchain_openai import AzureChatOpenAI
from config import Config


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
    )


async def get_exchange_rate() -> float:
    """Fetch current EUR to USD exchange rate."""
    return 1.08


def convert_eur_to_usd(eur: float, rate: float) -> float:
    return eur * rate


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

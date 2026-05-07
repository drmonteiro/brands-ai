"""
Utility functions for LangGraph nodes.
"""
from typing import List, Optional
import re
from urllib.parse import urlparse
from langchain_openai import AzureChatOpenAI
from tavily import TavilyClient
from config import Config

def get_llm(fast: bool = False, temperature: float = 0.3) -> AzureChatOpenAI:
    """
    Get Azure OpenAI LLM instance.
    
    Args:
        fast: If True, use the fast/cheap model (GPT-5.1-codex-mini) for triage.
              If False, use the deep model (GPT-5.1) for final analysis.
        temperature: Sampling temperature (lower = more deterministic)
    
    Returns:
        AzureChatOpenAI instance configured for the selected model tier.
    """
    deployment = Config.AZURE_OPENAI_DEPLOYMENT_FAST if fast else Config.AZURE_OPENAI_DEPLOYMENT
    
    # NEW: Newer Azure models (like gpt-5-mini) require temperature=1.0 
    # and fail if 0.0 is provided. We force 1.0 to avoid the "Error 400"
    safe_temperature = 1.0 if "mini" in deployment or "gpt-5" in deployment else temperature
    
    return AzureChatOpenAI(
        azure_endpoint=Config.AZURE_OPENAI_ENDPOINT,
        api_key=Config.AZURE_OPENAI_API_KEY,
        api_version=Config.AZURE_OPENAI_API_VERSION,
        deployment_name=deployment,
        temperature=safe_temperature,
        max_tokens=12000,
    )

def get_tavily_client() -> TavilyClient:
    """Get Tavily client instance"""
    return TavilyClient(api_key=Config.TAVILY_API_KEY)

async def get_exchange_rate() -> float:
    """Fetch current EUR to USD exchange rate"""
    # For now, use a fixed rate. In production, call an exchange rate API
    return 1.08

def convert_eur_to_usd(eur: float, rate: float) -> float:
    """Convert EUR to USD"""
    return eur * rate

def normalize_url(url: str) -> str:
    """Normalize URL for comparison to detect duplicates"""
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
    """
    Extract base domain from URL.
    E.g. https://www.tomjames.com/locations -> tomjames.com
    """
    if not url: return ""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return url

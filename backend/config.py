"""
Configuration and environment variables
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # Azure OpenAI
    AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
    AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
    AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
    AZURE_OPENAI_EMBEDDING_DEPLOYMENT = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-small")
    
    # Model deployments — 2-tier strategy
    # Deep model: GPT-5.1 (or GPT-4o as fallback) — used for final analysis in small batches
    AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT")  # Primary/deep model
    # Fast model: GPT-5.1-codex-mini (or GPT-4o-mini as fallback) — used for cheap triage
    AZURE_OPENAI_DEPLOYMENT_FAST = os.getenv("AZURE_OPENAI_DEPLOYMENT_FAST", os.getenv("AZURE_OPENAI_DEPLOYMENT"))
    
    # Tavily
    TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
    
    # Firecrawl
    FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")
    
    # Resend
    RESEND_API_KEY = os.getenv("RESEND_API_KEY")
    FROM_EMAIL = os.getenv("FROM_EMAIL", "onboarding@resend.dev")
    
    # LangSmith (optional)
    LANGCHAIN_TRACING_V2 = os.getenv("LANGCHAIN_TRACING_V2", "false")
    LANGCHAIN_API_KEY = os.getenv("LANGCHAIN_API_KEY")
    LANGCHAIN_PROJECT = os.getenv("LANGCHAIN_PROJECT", "confecos-lanca")
    
    # Database
    SYNC_DATABASE_URL = os.getenv("SYNC_DATABASE_URL")
    
    @classmethod
    def is_langsmith_enabled(cls) -> bool:
        return cls.LANGCHAIN_TRACING_V2.lower() == "true" and cls.LANGCHAIN_API_KEY is not None


# Current clients of Confeções Lança (for query generation)
CURRENT_CLIENTS = [
    {
        "name": "Carlos Nieto",
        "country": "Peru",
        "description": "Premium menswear retailer in South America, focuses on European-quality suits",
        "characteristics": ["Premium pricing", "European style", "South American market"],
    },
    {
        "name": "Grupo Yes",
        "country": "Spain/Portugal",
        "description": "Multi-brand fashion group with focus on quality menswear",
        "characteristics": ["Multi-brand", "Quality focus", "Iberian market"],
    },
    {
        "name": "Hawes & Curtis",
        "country": "United Kingdom",
        "description": "British heritage menswear brand known for shirts and suits since 1913",
        "characteristics": ["Heritage brand", "British style", "Premium quality", "Over 100 years history"],
    },
]

# Ideal client profile for Confeções Lança
CONFECOS_LANCA_PROFILE = """
Confeções Lança is a Portuguese manufacturer specializing in quality men's tailored clothing: suits, trousers, and waistcoats.

IDEAL CLIENT PROFILE:
- Independent menswear retailers and boutiques (NOT large department stores or chains)
- Focus on MID-TO-HIGH range segment with the following price ranges:
  • Complete suits (jacket + trousers): €500–€1,700
  • Jackets only: €300–€1,000
  • Trousers only: €250–€750
- NOT ultra-luxury/bespoke ateliers (e.g., Savile Row level is too high-end)
- Prefer brands with fewer than 20 physical stores (easier to establish partnership)
- Brands that sell tailored suits AND/OR separate pieces (jackets, trousers, waistcoats) with a tailoring/sartorial identity
- Brands with own label collections or interested in private label/white-label production
- Value quality European manufacturing at competitive prices
- MUST be headquartered in the target city (not just having a physical store there)

WHAT WE OFFER:
- Quality suits, trousers, and waistcoats manufactured in Portugal
- Competitive pricing for the mid-to-high segment
- Flexible minimum order quantities
- Own label collection production and private label options
- European craftsmanship with modern techniques

TARGET MARKETS:
- United Kingdom, USA, Germany, France, Nordic countries
- Growing interest in South America and Middle East
- Mid-to-high range tailored menswear retailers
- Price targets: Suits €500–€1,700 | Jackets €300–€1,000 | Trousers €250–€750
"""

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
    AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
    AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT")
    AZURE_OPENAI_EMBEDDING_DEPLOYMENT = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-small")
    
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
Confeções Lança is a Portuguese manufacturer specializing in high-quality men's suits and formal wear.

IDEAL CLIENT PROFILE:
- Boutique menswear retailers (not large department stores)
- Focus on premium/luxury segment (suits €500+)
- Prefer brands with fewer than 20 physical stores (easier to establish partnership)
- Value quality European manufacturing
- Looking for reliable, long-term manufacturing partners
- Interested in private label or white-label production

WHAT WE OFFER:
- High-quality suits manufactured in Portugal
- Competitive pricing for premium quality
- Flexible minimum order quantities
- Customization and private label options
- European craftsmanship with modern techniques

TARGET MARKETS:
- United Kingdom, USA, Germany, France, Nordic countries
- Growing interest in South America and Middle East
- Premium/luxury segment retailers
"""

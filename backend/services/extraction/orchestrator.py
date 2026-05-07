import logging
from typing import Tuple, Dict, Any, List
from services.crawl4ai_client import Crawl4AIResponse, Crawl4AIClient
from services.extraction.css_extractor import (
    css_extractor, 
    ExtractedBoutiqueData,
    REASON_NO_PRICES,
    REASON_PRICES_OUT_OF_RANGE,
    REASON_PRICES_TYPE_MISMATCH,
    REASON_NO_STORES,
    REASON_NO_BRAND
)
from services.extraction.llm_extractor import llm_extractor

logger = logging.getLogger(__name__)

REASON_TO_FIELD = {
    REASON_NO_PRICES: "prices",
    REASON_PRICES_OUT_OF_RANGE: "prices",
    REASON_PRICES_TYPE_MISMATCH: "prices",
    REASON_NO_STORES: "store_addresses",
    REASON_NO_BRAND: "brand_name",
}

def merge_extractions(
    css_result: ExtractedBoutiqueData,
    llm_result: ExtractedBoutiqueData,
) -> ExtractedBoutiqueData:
    """
    Funde resultados das duas camadas. Em caso de conflito, prioriza
    CSS (mais determinista) exceto quando CSS tem campo vazio.
    """
    return ExtractedBoutiqueData(
        prices=css_result.prices or llm_result.prices or [],
        store_addresses=(
            css_result.store_addresses
            or llm_result.store_addresses
            or []
        ),
        brand_name=css_result.brand_name or llm_result.brand_name,
    )

def merge_all_page_extractions(
    extractions: List[Dict[str, Any]],
) -> ExtractedBoutiqueData:
    """
    Funde extracções de múltiplas páginas do mesmo site.
    """
    all_prices = []
    all_stores = []
    brand = None

    for ext in extractions:
        data = ext["data"]
        page_type = ext["type"]

        if data.prices:
            all_prices.extend(data.prices)

        if data.store_addresses:
            all_stores.extend(data.store_addresses)

        # Brand: prioridade homepage > about > produto
        if data.brand_name and not brand:
            if page_type in ("homepage", "about"):
                brand = data.brand_name

    # Se não apanhámos brand de homepage/about, aceitar de produto
    if not brand:
        for ext in extractions:
            if ext["data"].brand_name:
                brand = ext["data"].brand_name
                break

    # Deduplicar preços (mesmo valor + moeda = duplicado)
    seen_prices = set()
    unique_prices = []
    for p in all_prices:
        key = (p.value, p.currency)
        if key not in seen_prices:
            seen_prices.add(key)
            unique_prices.append(p)

    # Deduplicar stores por cidade e morada parcial
    seen_cities = set()
    unique_stores = []
    for s in all_stores:
        key = (s.city.lower(), s.country.lower(), s.address[:10].lower() if s.address else "")
        if key not in seen_cities:
            seen_cities.add(key)
            unique_stores.append(s)

    # Determinar a fonte dominante
    sources = [ext["data"].price_source for ext in extractions if ext["data"].price_source]
    if "llm" in sources and "css" in sources:
        source = "mixed"
    elif "llm" in sources:
        source = "llm"
    elif "css" in sources:
        source = "css"
    else:
        source = "none"

    return ExtractedBoutiqueData(
        prices=unique_prices,
        store_addresses=unique_stores,
        brand_name=brand,
        price_source=source
    )

async def extract_boutique_data(response: Crawl4AIResponse) -> Tuple[ExtractedBoutiqueData, Dict[str, Any]]:
    """
    Orchestrates the 2-layer extraction strategy for a single page.
    Returns (ExtractedBoutiqueData, token_usage_dict).
    """
    if not response.success or not response.cleaned_html:
        logger.warning("[ORCHESTRATOR] Invalid response, returning empty extraction.")
        return ExtractedBoutiqueData(), {"total_tokens": 0, "cost_usd": 0}

    # Camada 1: tentar CSS local
    css_result = css_extractor.extract(response.cleaned_html)
    score, reasons = css_extractor.extraction_quality_score(css_result)

    if score >= 0.7:
        logger.info(f"[ORCHESTRATOR] Camada 1 OK (score={score})")
        css_result.price_source = "css"
        return css_result, {"total_tokens": 0, "cost_usd": 0}

    # Determine missing fields for partial extraction based on score reasons explicitly
    missing_fields = list({
        REASON_TO_FIELD[r]
        for r in reasons
        if r in REASON_TO_FIELD
    })

    # Camada 2: fallback para LLM
    logger.warning(
        f"[ORCHESTRATOR] Camada 1 insuficiente (score={score}, razões={reasons}), "
        f"acionando LLM extraction"
    )
    
    # Send best_markdown to save tokens
    llm_result, token_usage = await llm_extractor.extract(
        markdown=response.best_markdown,
        partial_extraction=css_result,
        missing_fields=missing_fields
    )
    
    final_result = merge_extractions(css_result, llm_result)
    
    # Tagging the source
    if score > 0.3:
        final_result.price_source = "mixed"
    else:
        final_result.price_source = "llm"
        
    return final_result, token_usage

async def full_site_extraction_flow(client: Crawl4AIClient, url: str) -> Tuple[ExtractedBoutiqueData, Dict[str, Any], str]:
    """
    Fluxo completo: prefetch multi-página -> extração -> merge.
    Retorna (dados, tokens, homepage_markdown).
    """
    # Passo 1: Descoberta de URLs (Prefetch já faz um scrape da homepage)
    logger.info(f"[FULL_FLOW] Iniciando prefetch para {url}")
    all_urls = await client.prefetch_map(url)
    logger.info(f"[FULL_FLOW] Descobertas {len(all_urls)} URLs em {url}")

    # Passo 2: Classificar URLs
    product_urls = [u for u in all_urls if any(kw in u.lower() for kw in ["/product", "/shop", "/collection", "/suit", "/blazer", "/jacket", "/tailoring", "/catalog", "/men"])]
    store_urls = [u for u in all_urls if any(kw in u.lower() for kw in ["store", "boutique", "location", "find-us", "stockist", "shop-locator", "contact"])]
    about_urls = [u for u in all_urls if any(kw in u.lower() for kw in ["about", "story", "heritage", "history"])]

    logger.info(f"[FULL_FLOW] Classificação: {len(product_urls)} produto, {len(store_urls)} store, {len(about_urls)} about")

    # Passo 3: Scrape seletivo
    pages_to_scrape = {
        "homepage": [url],
        "product": product_urls[:5], 
        "store": store_urls[:2],
        "about": about_urls[:1],
    }

    all_extractions = []
    total_tokens = 0
    total_cost = 0.0
    homepage_markdown = ""

    scraped_urls = set()

    for page_type, urls in pages_to_scrape.items():
        for page_url in urls:
            if page_url in scraped_urls: continue
            scraped_urls.add(page_url)
            
            logger.info(f"[FULL_FLOW] Scraping {page_type}: {page_url}")
            response = await client.scrape(page_url)
            if not response.success:
                logger.warning(f"Falha no scrape de {page_url}")
                continue

            if page_type == "homepage":
                homepage_markdown = response.best_markdown

            result, tokens = await extract_boutique_data(response)
            total_tokens += tokens.get("total_tokens", 0)
            total_cost += tokens.get("cost_usd", 0.0)
            
            all_extractions.append({
                "type": page_type,
                "url": page_url,
                "data": result
            })

    final_result = merge_all_page_extractions(all_extractions)
    return final_result, {"total_tokens": total_tokens, "cost_usd": total_cost}, homepage_markdown

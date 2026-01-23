"""
LangGraph-based Prospector Agent for Confeções Lança

This agent orchestrates the lead generation workflow:
1. Client Analysis: Analyze current clients to understand ideal profile
2. Query Generation: AI generates 10 search queries based on client patterns
3. Discovery: Search Tavily with 10 queries × 10 results = 100 potential URLs
4. Selection Agent: Pick best candidate from each query (10 selected)
5. Final Selection: Return up to 10 unique qualified candidates
6. Human-in-the-Loop: Wait for approval
7. Email: Send partnership proposals
"""

import json
import re
import asyncio
from datetime import datetime
from typing import List, Optional, Dict, Any
from urllib.parse import urlparse

from langchain_openai import AzureChatOpenAI
from tavily import TavilyClient

from models import (
    ProspectorState, BrandLead, QuerySearchResults, 
    SelectedCandidate, ExtractedContent
)
from config import (
    Config, CURRENT_CLIENTS, CONFECOS_LANCA_PROFILE
)


# ============================================================================
# LLM AND CLIENT INITIALIZATION
# ============================================================================

def get_llm() -> AzureChatOpenAI:
    """Get Azure OpenAI LLM instance"""
    endpoint = Config.AZURE_OPENAI_ENDPOINT or ""
    instance_name = endpoint.replace("https://", "").replace(".openai.azure.com/", "")
    
    return AzureChatOpenAI(
        azure_endpoint=Config.AZURE_OPENAI_ENDPOINT,
        api_key=Config.AZURE_OPENAI_API_KEY,
        api_version=Config.AZURE_OPENAI_API_VERSION,
        deployment_name=Config.AZURE_OPENAI_DEPLOYMENT,
        temperature=0.3,
    )


def get_tavily_client() -> TavilyClient:
    """Get Tavily client instance"""
    return TavilyClient(api_key=Config.TAVILY_API_KEY)


# Storage for search results (used between nodes)
search_results_by_query: List[QuerySearchResults] = []


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

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
    except:
        return url.lower().strip()


# ============================================================================
# NODE 1: INITIALIZE SEARCH
# ============================================================================

async def initialize_search(state: ProspectorState) -> Dict[str, Any]:
    """
    Initialize search and generate queries using AI based on current clients.
    
    This agent analyzes existing clients (Carlos Nieto, Grupo Yes, Hawes & Curtis)
    and generates 10 intelligent search queries to find similar brands.
    """
    print(f"[INIT] Starting intelligent search for: {state.target_city}")
    
    progress = list(state.progress)
    
    # Fetch current exchange rate
    exchange_rate = await get_exchange_rate()
    price_threshold_usd = convert_eur_to_usd(state.price_threshold_eur, exchange_rate)
    
    progress.append(f"🚀 Pesquisa iniciada para {state.target_city}. Preço alvo: ${price_threshold_usd:.0f}")
    progress.append("🔍 Analisando clientes atuais para gerar queries inteligentes...")
    
    # Use AI to generate queries based on current clients
    search_queries = await generate_queries_from_clients(state.target_city)
    
    progress.append(f"✅ {len(search_queries)} queries geradas pelo agente de análise")
    
    # Log queries for visibility
    for idx, query in enumerate(search_queries):
        progress.append(f"   Query {idx + 1}: \"{query}\"")
    
    return {
        "exchange_rate": exchange_rate,
        "price_threshold_usd": price_threshold_usd,
        "search_queries": search_queries,
        "progress": progress,
    }


async def generate_queries_from_clients(target_city: str) -> List[str]:
    """
    AI Agent: Generate 10 search queries based on current client analysis.
    
    Analyzes: Carlos Nieto (Peru), Grupo Yes (Spain), Hawes & Curtis (UK)
    Generates diverse queries to find similar potential partners.
    """
    llm = get_llm()
    
    clients_description = "\n".join([
        f"- {c['name']} ({c['country']}): {c['description']}. Characteristics: {', '.join(c['characteristics'])}"
        for c in CURRENT_CLIENTS
    ])
    
    prompt = f"""You are a B2B sales intelligence agent for Confeções Lança, a Portuguese suit manufacturer.

CURRENT CLIENTS (analyze these to understand ideal client profile):
{clients_description}

WHAT CONFEÇÕES LANÇA IS LOOKING FOR:
{CONFECOS_LANCA_PROFILE}

TARGET CITY FOR SEARCH: {target_city}

YOUR TASK:
Generate exactly 3 different search queries to find potential menswear retailers/brands in {target_city} that would be similar to our current clients.

QUERY GENERATION RULES:
1. Each query must be different and target a different angle
2. Include the city name in each query
3. Focus on: boutique menswear, premium suits, luxury brands, independent retailers, heritage brands, bespoke tailors
4. Make queries broad enough to find many quality results

RETURN FORMAT:
Return ONLY a JSON array of 3 strings, nothing else:
["query 1", "query 2", "query 3"]

Example:
["{target_city} luxury menswear boutique suits", "{target_city} premium custom tailor bespoke suits", "{target_city} high end men suits store"]"""

    print("[QUERY-AGENT] Generating intelligent queries based on client analysis...")
    
    response = await llm.ainvoke(prompt)
    response_text = response.content if isinstance(response.content, str) else str(response.content)
    cleaned_response = response_text.strip().replace("```json", "").replace("```", "").strip()
    
    try:
        queries = json.loads(cleaned_response)
        if isinstance(queries, list) and len(queries) >= 2:
            print(f"[QUERY-AGENT] Generated {len(queries)} queries")
            return queries[:3]  # Ensure max 3
    except json.JSONDecodeError as e:
        print(f"[QUERY-AGENT] Failed to parse queries, using fallback: {e}")
    
    # Fallback queries if AI fails (3 queries)
    return [
        f'{target_city} luxury menswear boutique premium suits',
        f'{target_city} custom tailor bespoke suits high end',
        f'{target_city} men suits store designer brand',
    ]


# ============================================================================
# NODE 2: DISCOVERY
# ============================================================================

async def discovery_node(state: ProspectorState) -> Dict[str, Any]:
    """
    Discovery - Find potential brand URLs using REAL web search with Tavily.
    
    Configuration: 
    - Executes 3 queries
    - Retrieves 20 results per query (60 total potential URLs)
    - Stores results per query for intelligent selection
    """
    global search_results_by_query
    
    print("[DISCOVERY] Starting Tavily search with 3 queries × 20 results...")
    
    candidate_urls: List[str] = []
    unique_urls: set = set()
    progress = list(state.progress)
    
    # Reset search results storage
    search_results_by_query = []
    
    try:
        total_queries = len(state.search_queries)
        progress.append(f"🔍 Iniciando busca com {total_queries} queries (20 resultados cada)...")
        progress.append(f"📊 Total potencial: até {total_queries * 20} URLs")
        
        client = get_tavily_client()
        
        # Excluded domains
        exclude_domains = [
            "amazon.com", "ebay.com", "walmart.com", "target.com",
            "macys.com", "nordstrom.com", "asos.com", "zalando.com",
            "wikipedia.org", "facebook.com", "instagram.com", "twitter.com",
            "linkedin.com", "youtube.com", "pinterest.com", "yelp.com"
        ]
        
        # Execute 3 queries with 20 results each
        for i in range(min(total_queries, 3)):
            query = state.search_queries[i]
            query_start_time = datetime.now()
            
            try:
                print(f"[TAVILY] Query {i + 1}/{min(total_queries, 3)}: \"{query}\"")
                progress.append(f"🔎 Query {i + 1}: \"{query}\"")
                
                response = client.search(
                    query=query,
                    search_depth="advanced",
                    max_results=20,  # 20 results per query
                    exclude_domains=exclude_domains,
                )
                
                query_duration = (datetime.now() - query_start_time).total_seconds() * 1000
                
                # Store results for this query
                query_results = QuerySearchResults(
                    query_index=i,
                    query=query,
                    results=[]
                )
                
                # Collect results
                for result in response.get("results", []):
                    url = result.get("url", "")
                    if url and url not in unique_urls:
                        unique_urls.add(url)
                        candidate_urls.append(url)
                        
                        query_results.results.append({
                            "url": url,
                            "title": result.get("title", ""),
                            "content": result.get("content", ""),
                        })
                
                search_results_by_query.append(query_results)
                
                results_count = len(response.get("results", []))
                progress.append(f"   ✓ {results_count} resultados ({query_duration:.0f}ms)")
                
            except Exception as query_error:
                print(f"[TAVILY] Error with query {i + 1} \"{query}\": {query_error}")
                progress.append(f"   ⚠️ Query {i + 1} falhou, continuando...")
                
                # Still add empty result to maintain query count
                search_results_by_query.append(QuerySearchResults(
                    query_index=i,
                    query=query,
                    results=[]
                ))
        
        # Summary
        total_results = sum(len(q.results) for q in search_results_by_query)
        progress.append(f"\n📈 RESUMO DA BUSCA TAVILY:")
        progress.append(f"   • Queries executadas: {len(search_results_by_query)}")
        progress.append(f"   • URLs únicos encontrados: {len(candidate_urls)}")
        progress.append(f"   • Total de resultados: {total_results}")
        
        print(f"[DISCOVERY] Complete: {len(candidate_urls)} unique URLs from {len(search_results_by_query)} queries")
        
        if len(candidate_urls) == 0:
            progress.append("⚠️ Nenhum candidato encontrado. Tente outra cidade ou verifique créditos Tavily.")
        
        return {
            "candidate_urls": candidate_urls,
            "progress": progress,
        }
        
    except Exception as error:
        print(f"[DISCOVERY] Fatal error: {error}")
        return {
            "error": f"Descoberta falhou: {str(error)}",
            "progress": progress + ["❌ Descoberta falhou - Verifique API key do Tavily e créditos"],
        }


# ============================================================================
# NODE 3: VALIDATION (SELECTION AGENT)
# ============================================================================

async def validation_node(state: ProspectorState) -> Dict[str, Any]:
    """
    Selection Agent - Pick 5 best candidates from each query.
    
    Workflow:
    1. For each of the 3 queries, the agent selects the 5 BEST candidates
    2. This gives us 15 pre-selected URLs (5 from each search)
    3. Then a final agent analyzes all 15 and returns those that are interesting
    """
    global search_results_by_query
    
    print("[VALIDATION] Starting intelligent selection with AI agents...")
    
    progress = list(state.progress)
    
    if not search_results_by_query:
        return {
            "potential_brands": [],
            "progress": progress + ["⚠️ Nenhum resultado de busca para processar"],
        }
    
    try:
        # ====================================================================
        # STEP 1: Selection Agent picks 5 best URLs from each query
        # ====================================================================
        progress.append(f"\n🤖 AGENTE DE SELEÇÃO - Fase 1: Escolher 5 de cada busca")
        progress.append(f"   Analisando {len(search_results_by_query)} queries...")
        
        selected_from_each_query = await select_best_from_each_query(search_results_by_query)
        
        progress.append(f"   ✅ {len(selected_from_each_query)} candidatos pré-selecionados:")
        for idx, selection in enumerate(selected_from_each_query):
            progress.append(f"   {idx + 1}. [Query {selection.query_index + 1}] {selection.url}")
            progress.append(f"      Razão: {selection.reason}")
        
        if not selected_from_each_query:
            return {
                "potential_brands": [],
                "progress": progress + ["⚠️ Nenhum candidato selecionado pelo agente"],
            }
        
        # ====================================================================
        # STEP 2: Extract content from selected URLs
        # ====================================================================
        progress.append(f"\n📥 Extraindo conteúdo dos {len(selected_from_each_query)} candidatos selecionados...")
        
        urls_to_extract = [s.url for s in selected_from_each_query]
        extracted_contents = await batch_extract_content(urls_to_extract)
        
        successful_extractions = [e for e in extracted_contents if e.content]
        progress.append(f"   ✅ Conteúdo extraído de {len(successful_extractions)}/{len(urls_to_extract)} sites")
        
        if not successful_extractions:
            return {
                "potential_brands": [],
                "progress": progress + ["⚠️ Nenhum conteúdo extraído dos sites selecionados"],
            }
        
        # ====================================================================
        # STEP 3: Final Agent analyzes and returns interesting brands
        # ====================================================================
        progress.append(f"\n🏆 AGENTE DE SELEÇÃO - Fase 2: Analisar e selecionar marcas interessantes")
        
        final_selection = await select_final_candidates(
            successful_extractions,
            state.price_threshold_usd,
            state.target_city
        )
        
        progress.append(f"   ✅ {len(final_selection)} MARCAS INTERESSANTES encontradas:")
        for idx, brand in enumerate(final_selection):
            progress.append(f"\n   {idx + 1}. {brand.name}")
            progress.append(f"      🌐 {brand.website_url}")
            progress.append(f"      💼 {brand.brand_style}")
            if brand.average_suit_price_usd > 0:
                progress.append(f"      💰 ${brand.average_suit_price_usd}")
            progress.append(f"      📝 {brand.company_overview[:100]}...")
        
        return {
            "potential_brands": final_selection,
            "candidate_urls": urls_to_extract,
            "progress": progress,
        }
        
    except Exception as error:
        print(f"[VALIDATION] Selection agent error: {error}")
        return {
            "potential_brands": [],
            "progress": progress + [f"❌ Erro na seleção: {str(error)}"],
        }


async def select_best_from_each_query(query_results: List[QuerySearchResults]) -> List[SelectedCandidate]:
    """
    Selection Agent: Pick the 5 BEST candidates from each query's results.
    
    For each of the 3 queries, analyzes the 20 results and picks the 5 best matches
    based on Confeções Lança's ideal client profile.
    """
    llm = get_llm()
    selected: List[SelectedCandidate] = []
    
    print(f"[SELECTION-AGENT] Analyzing {len(query_results)} queries to pick 5 best from each...")
    
    # Build queries content
    queries_content = "\n\n".join([
        f"""
=== QUERY {q.query_index + 1}: "{q.query}" ===
Results:
{chr(10).join([f'''
  {i + 1}. URL: {r['url']}
     Title: {r['title']}
     Preview: {r['content'][:300]}...
''' for i, r in enumerate(q.results)])}
"""
        for q in query_results if q.results
    ])
    
    clients_list = "\n".join([
        f"- {c['name']} ({c['country']}): {', '.join(c['characteristics'])}"
        for c in CURRENT_CLIENTS
    ])
    
    selection_prompt = f"""You are a B2B sales intelligence agent for Confeções Lança, a Portuguese suit manufacturer looking for partnership opportunities.

{CONFECOS_LANCA_PROFILE}

CURRENT CLIENTS (for reference - find similar businesses):
{clients_list}

YOUR TASK:
From EACH query's results below, select the TOP 5 most interesting candidates for potential partnership.

SELECTION CRITERIA (in order of importance):
1. Must be a menswear brand/retailer that sells suits or formalwear
2. Prefer luxury, premium, or boutique brands
3. Prefer official brand websites (not directories or marketplaces)
4. Prefer independent/boutique stores over large chains
5. Interesting brands even without visible prices are OK (bespoke tailors often don't show prices)

⛔ AVOID:
- Blog/news/press pages
- Social media links
- Review sites (yelp, tripadvisor)
- Large department stores (nordstrom, macys, etc.)
- Fast fashion brands

QUERIES AND RESULTS:
{queries_content}

RETURN FORMAT:
Return a JSON array with UP TO 5 selections per query:
[
  {{
    "queryIndex": 0,
    "url": "selected url",
    "reason": "Brief reason why this brand is interesting"
  }},
  ...
]

Return at least 10-15 total selections across all queries."""

    response = await llm.ainvoke(selection_prompt)
    response_text = response.content if isinstance(response.content, str) else str(response.content)
    cleaned_response = response_text.strip().replace("```json", "").replace("```", "").strip()
    
    try:
        selections = json.loads(cleaned_response)
        
        if isinstance(selections, list):
            # Track URLs we've already selected to avoid duplicates across queries
            selected_urls: set = set()
            
            # Patterns that indicate BAD URLs (never have prices)
            bad_url_patterns = [
                '/blog', '/news', '/press', '/article',
                '/about', '/about-us', '/our-story', '/our-team',
                '/contact', '/locations', '/find-us', '/store-locator',
                '/tagged', '/category', '/page-', '/tag/',
                'facebook.com', 'instagram.com', 'twitter.com', 'linkedin.com',
                'yelp.com', 'tripadvisor.com', 'google.com/maps',
            ]
            
            for sel in selections:
                query_result = next((q for q in query_results if q.query_index == sel.get("queryIndex")), None)
                
                if query_result and sel.get("url"):
                    url_lower = sel["url"].lower()
                    
                    # Check if URL contains BAD patterns - SKIP these!
                    has_bad_pattern = any(pattern in url_lower for pattern in bad_url_patterns)
                    if has_bad_pattern:
                        print(f"[SELECTION-AGENT] ⚠️ SKIPPING bad URL pattern: {sel['url']}")
                        continue
                    
                    # Normalize URL for comparison
                    normalized_url = normalize_url(sel["url"])
                    
                    # Skip if we've already selected this URL from another query
                    if normalized_url in selected_urls:
                        print(f"[SELECTION-AGENT] Skipping duplicate URL: {sel['url']}")
                        continue
                    
                    selected_urls.add(normalized_url)
                    
                    # Find title from results
                    title = ""
                    for r in query_result.results:
                        if r["url"] == sel["url"]:
                            title = r["title"]
                            break
                    
                    selected.append(SelectedCandidate(
                        query_index=sel.get("queryIndex", 0),
                        url=sel["url"],
                        title=title,
                        reason=sel.get("reason", "Selected as best match"),
                    ))
    
    except json.JSONDecodeError as e:
        print(f"[SELECTION-AGENT] Failed to parse selections: {e}")
    
    print(f"[SELECTION-AGENT] Selected {len(selected)} UNIQUE candidates from {len(query_results)} queries")
    return selected


async def batch_extract_content(urls: List[str]) -> List[ExtractedContent]:
    """
    Batch extract content from multiple URLs using Tavily Extract API.
    """
    client = get_tavily_client()
    results: List[ExtractedContent] = []
    
    print(f"[BATCH EXTRACT] Extracting content from {len(urls)} URLs using TAVILY EXTRACT API...")
    
    try:
        extraction = client.extract(urls=urls)
        
        if extraction.get("results"):
            for result in extraction["results"]:
                raw_content = result.get("raw_content", "")
                # Truncate content (max ~12000 chars)
                truncated_content = raw_content[:12000] if raw_content else None
                
                results.append(ExtractedContent(
                    url=result.get("url", ""),
                    content=truncated_content,
                ))
                
                print(f"[EXTRACT] {result.get('url', 'unknown')}: {len(raw_content)} chars → {len(truncated_content or '')} chars")
        
        # Add failed extractions for URLs that didn't return
        extracted_urls = {r.url for r in results}
        for url in urls:
            if url not in extracted_urls:
                results.append(ExtractedContent(url=url, content=None))
        
    except Exception as error:
        print(f"[BATCH EXTRACT] Error: {error}")
        return [ExtractedContent(url=url, content=None) for url in urls]
    
    print(f"[BATCH EXTRACT] Successfully extracted {len([r for r in results if r.content])}/{len(urls)} sites")
    return results


async def select_final_candidates(
    extracted_contents: List[ExtractedContent],
    price_threshold: float,
    target_city: str
) -> List[BrandLead]:
    """
    Final Selection Agent: Analyze and return up to 10 unique qualified candidates.
    
    Takes the ~10 pre-selected URLs and validates each one.
    Returns all that pass the filters (suits + price found + price >= threshold).
    """
    llm = get_llm()
    
    # Build content for analysis
    sites_content = "\n\n".join([
        f"""
=== CANDIDATE {idx + 1} ===
URL: {e.url}
CONTENT:
{e.content}
"""
        for idx, e in enumerate(extracted_contents) if e.content
    ])
    
    analysis_prompt = f"""You are the FINAL selection agent for Confeções Lança. Your job is to analyze ALL candidates and return those that could be interesting partnership opportunities.

{CONFECOS_LANCA_PROFILE}

WHAT WE'RE LOOKING FOR:
- Menswear brands that sell suits or formalwear
- Luxury, premium, or boutique positioning
- Independent brands (not large department stores)
- Brands that might be interested in Portuguese manufacturing partnership

CANDIDATES TO EVALUATE:
{sites_content}

YOUR TASK:
1. Analyze EACH candidate
2. Return ALL brands that seem like interesting partnership opportunities
3. Include brands even if prices are not shown (bespoke tailors often don't display prices)
4. Be GENEROUS - if in doubt, include the brand

PRICE RULES:
- If you find actual prices in the content, include them
- If prices are not shown (common for bespoke/custom tailors), set avgPrice to 0 and priceSource to "not_public"
- Do NOT reject brands just because prices are not visible

RETURN FORMAT - JSON array (include ALL interesting brands, up to 15):
[
  {{
    "rank": 1,
    "url": "url",
    "name": "Brand Name",
    "storeCount": estimated number or 1,
    "avgPrice": price in USD if found, or 0 if not visible,
    "priceSource": "found" | "not_public",
    "priceNote": "Price info if found, or 'Prices not displayed publicly'",
    "siteType": "official" or "third-party",
    "isUSBased": true/false,
    "city": "{target_city}",
    "clothingTypes": ["Suits", ...other items],
    "brandStyle": "Luxury/Premium/Bespoke/Contemporary/etc",
    "businessModel": "Retail/Bespoke/Both",
    "whySelected": "Why this brand could be an interesting partner for Confeções Lança",
    "fitScore": 1-10
  }}
]

IMPORTANT: Return at least 5-10 brands. Be generous in your selection!

Return ONLY the JSON array, no other text."""

    print(f"[SELECTION-AGENT] Analyzing {len(extracted_contents)} candidates for qualification...")
    
    response = await llm.ainvoke(analysis_prompt)
    response_text = response.content if isinstance(response.content, str) else str(response.content)
    cleaned_response = response_text.strip().replace("```json", "").replace("```", "").strip()
    
    # DEBUG: Print raw LLM response
    print(f"\n{'='*60}")
    print(f"[DEBUG] RAW LLM RESPONSE (first 2000 chars):")
    print(f"{'='*60}")
    print(cleaned_response[:2000])
    print(f"{'='*60}\n")
    
    try:
        candidates = json.loads(cleaned_response)
        
        print(f"\n{'='*60}")
        print(f"[DEBUG] LLM returned {len(candidates) if isinstance(candidates, list) else 'NOT A LIST'} candidates")
        print(f"{'='*60}")
        
        if not isinstance(candidates, list):
            print("[SELECTION-AGENT] Response is not an array, returning empty")
            return []
        
        # DEBUG: Show what LLM returned
        for idx, c in enumerate(candidates):
            print(f"\n[DEBUG] Candidate {idx+1}: {c.get('name', 'UNNAMED')}")
            print(f"  - sellsSuits: {c.get('sellsSuits')}")
            print(f"  - priceSource: {c.get('priceSource')}")
            print(f"  - avgPrice: ${c.get('avgPrice', 0)}")
            print(f"  - clothingTypes: {c.get('clothingTypes', [])}")
        
        # Ensure unique URLs only - no duplicates allowed
        seen_urls: set = set()
        unique_results: List[BrandLead] = []
        
        for data in candidates:
            # Normalize URL for comparison
            normalized_url = normalize_url(data.get("url", ""))
            
            # Skip if we've already seen this URL or no valid URL
            if normalized_url in seen_urls or not data.get("url"):
                continue
            
            seen_urls.add(normalized_url)
            
            # Get data
            clothing_types = data.get("clothingTypes", ["Suits"])
            price_source = data.get("priceSource", "not_public")
            avg_price = data.get("avgPrice", 0)
            price_note = data.get("priceNote", "Prices not displayed")
            brand_style = data.get("brandStyle", "Unknown")
            
            # Determine price status
            if price_source == "found" and avg_price > 0:
                price_status = "verified"
                verified_price = avg_price
            else:
                price_status = "not_public"
                verified_price = 0
            
            print(f"\n[FILTER] ✅ ACCEPTED \"{data.get('name')}\"")
            print(f"  Style: {brand_style}")
            print(f"  Price: {'$' + str(avg_price) if avg_price > 0 else 'Not public'}")
            
            # Build verification log
            verification_log = [
                f"Rank: #{data.get('rank', len(unique_results) + 1)}",
                f"Fit Score: {data.get('fitScore', 'N/A')}/10",
                f"💰 Price: ${verified_price}" if verified_price > 0 else "⚠️ Prices not displayed publicly",
                f"📝 {price_note[:100]}" if price_note else "",
                f"🏪 Stores: {data.get('storeCount', 'unknown')}",
                f"👕 Style: {brand_style}",
            ]
            
            unique_results.append(BrandLead(
                name=data.get("name", "Unknown Brand"),
                website_url=data.get("url"),
                store_count=data.get("storeCount", 1) or 1,  # 0 means unknown, treat as 1
                average_suit_price_usd=verified_price,
                city=data.get("city", target_city),
                origin_country="USA" if data.get("isUSBased") else "International",
                verified=price_status == "verified",
                revenue=data.get("revenue", "Unknown"),
                clothing_types=clothing_types,
                target_gender=data.get("targetGender", "Men"),
                brand_style=brand_style,
                business_model=data.get("businessModel", "Retail"),
                company_overview=data.get("whySelected", "Selected as potential partner"),
                verification_log=verification_log,
                passes_constraints=True,
            ))
            
            if len(unique_results) >= 15:
                break
        
        print(f"[SELECTION-AGENT] Returning {len(unique_results)} interesting brands")
        return unique_results
        
    except json.JSONDecodeError as e:
        print(f"\n{'='*60}")
        print(f"[SELECTION-AGENT] ❌ FAILED TO PARSE LLM RESPONSE")
        print(f"Error: {e}")
        print(f"Response was: {cleaned_response[:1000]}")
        print(f"{'='*60}\n")
        return []


# ============================================================================
# NODE 4: FILTER
# ============================================================================

async def filter_node(state: ProspectorState) -> Dict[str, Any]:
    """
    Finalize the selected brands.
    """
    print("[FILTER] Finalizing selected brands...")
    
    verified_brands = state.potential_brands
    
    progress = list(state.progress)
    progress.append(f"\n🎯 RESULTADO FINAL: {len(verified_brands)} marcas interessantes encontradas")
    
    return {
        "verified_brands": verified_brands,
        "progress": progress,
    }


# ============================================================================
# MAIN WORKFLOW
# ============================================================================

async def run_prospector_workflow(initial_state: ProspectorState) -> ProspectorState:
    """
    Run the complete prospector workflow.
    """
    state = initial_state.model_copy()
    
    print(f"\n{'='*60}")
    print(f"[WORKFLOW] Starting prospector for: {state.target_city}")
    print(f"{'='*60}\n")
    
    try:
        # Node 1: Initialize
        updates = await initialize_search(state)
        state = state.model_copy(update=updates)
        
        # Node 2: Discovery
        updates = await discovery_node(state)
        state = state.model_copy(update=updates)
        
        if state.error:
            return state
        
        # Node 3: Validation
        updates = await validation_node(state)
        state = state.model_copy(update=updates)
        
        if state.error:
            return state
        
        # Node 4: Filter
        updates = await filter_node(state)
        state = state.model_copy(update=updates)
        
        return state
        
    except Exception as error:
        print(f"[WORKFLOW] Error: {error}")
        state.error = str(error)
        return state


def create_initial_state(city: str) -> ProspectorState:
    """Create initial state for a new prospecting session."""
    return ProspectorState(
        target_city=city,
        target_country="USA",
        search_queries=[],
        candidate_urls=[],
        potential_brands=[],
        verified_brands=[],
        approval_status={},
        email_logs=[],
        exchange_rate=1.08,
        price_threshold_eur=500,
        price_threshold_usd=540,
        max_stores=20,
        progress=[],
    )

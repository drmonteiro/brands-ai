import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

from models import ProspectorState
from agents.nodes.discovery import discovery_node
from services.content_scraper import batch_extract_content, enrich_content_with_prices
from services.price_extractor import extract_price_from_content
from models import ExtractedContent

async def main():
    state = {
        "target_city": "London",
        "search_queries": [
            "London independent menswear tailor boutique",
        ],
        "query_origins": ["B2B/PrivateLabel"]
    }
    
    print("--- TEST DISCOVERY (EXA) ---")
    res = await discovery_node(state)
    urls = res.get("candidate_urls", [])
    print(f"URLs Encontrados: {len(urls)}")
    if res.get("search_results") and res["search_results"][0].results:
        print(f"Exemplo snippet: {res['search_results'][0].results[0].get('content')[:150]}...")
    else:
        print("Sem snippets no resultado.")
        
    print("\n--- TEST SCRAPE (FIRECRAWL) ---")
    # Shopify test site
    test_urls = ["https://cdlp.com"]  # CDLP is a well known modern menswear/essentials site
    if len(urls) > 0:
        test_urls.append(urls[0])
        
    contents = await batch_extract_content(test_urls)
    for c in contents:
        print(f"URL: {c.url} - Size: {len(c.content)} chars")
        if len(c.content) > 500:
            print("Sucesso (Markdown limpo > 500 chars).")
            
    print("\n--- TEST PRICE EXTRACT (FIRECRAWL SCHEMA) ---")
    # test a known suit site with prices
    suit_site = ExtractedContent(url="https://eu.suitsupply.com/en-pt/men/suits", content="Suitsupply Suits Collection...")
    enriched = await enrich_content_with_prices([suit_site])
    print("Enriched Content Size:", len(enriched[0].content))
    
    price_info = extract_price_from_content(enriched[0].content)
    print("Price Extracted Info:", price_info)

if __name__ == "__main__":
    asyncio.run(main())

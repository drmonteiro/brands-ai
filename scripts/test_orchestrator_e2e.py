import asyncio
import os
import sys
from dotenv import load_dotenv

# Ensure we can import from backend
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))
load_dotenv(os.path.join(os.path.dirname(__file__), '..', 'backend', '.env'))

from services.crawl4ai_client import get_crawl4ai_client
from services.extraction.orchestrator import full_site_extraction_flow

async def test_e2e_full_flow():
    test_urls = [
        "https://www.huntsmansavilerow.com/", # UK Luxury
        "https://suitsupply.com/en-pt/",      # Global
        "https://www.isaia.it/"              # Italian
    ]
    
    print("\n| Site | Camada 2 acionada? | Total Tokens | Resultado Final Merged |")
    print("|------|--------------------|--------------|------------------------|")
    
    async for client in get_crawl4ai_client():
        for url in test_urls:
            try:
                print(f"\n[E2E] A processar fluxo completo para: {url}")
                final_data, tokens = await full_site_extraction_flow(client, url)
                
                token_count = tokens.get("total_tokens", 0)
                c2_acionada = "Sim" if token_count > 0 else "Não"
                
                final_str = (
                    f"Prices: {len(final_data.prices)}, "
                    f"Stores: {len(final_data.store_addresses)}, "
                    f"Brand: {final_data.brand_name}"
                )
                
                print(f"| {url} | {c2_acionada} | {token_count} | {final_str} |")
                
            except Exception as e:
                print(f"| {url} | Erro | N/A | Erro Fatal: {str(e)[:50]} |")

if __name__ == "__main__":
    asyncio.run(test_e2e_full_flow())

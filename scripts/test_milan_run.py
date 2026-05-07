import asyncio
import os
import sys
import time
from dotenv import load_dotenv

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))
load_dotenv(os.path.join(os.path.dirname(__file__), '..', 'backend', '.env'))

from agents.nodes.validator import validation_node
from models import ProspectorState, QuerySearchResults

async def test_milan_full_run():
    # 15 Milanese Boutiques / Brands
    milan_candidates = [
        {"url": "https://www.boglioliit.com/", "title": "Boglioli Milano"},
        {"url": "https://www.canali.com/it_it/", "title": "Canali Luxury Suits"},
        {"url": "https://www.palzileri.com/it/", "title": "Pal Zileri"},
        {"url": "https://www.corneliani.com/it/it/", "title": "Corneliani"},
        {"url": "https://www.carusomenswear.com/", "title": "Caruso Tailoring"},
        {"url": "https://www.larusmiani.it/", "title": "Larusmiani Via MonteNapoleone"},
        {"url": "https://www.bardellimilano.it/", "title": "Bardelli Milano"},
        {"url": "https://www.albazar.it/", "title": "Al Bazar Milano by Lino Ieluzzi"},
        {"url": "https://www.camiceriapiccolo.com/", "title": "Camiceria Piccolo"},
        {"url": "https://www.sartoriarossi.com/", "title": "Sartoria Rossi"},
        {"url": "https://www.piniparma.com/", "title": "Pini Parma"},
        {"url": "https://www.lanieri.com/it/", "title": "Lanieri Custom Suits"},
        {"url": "https://www.lucafaloni.com/", "title": "Luca Faloni"},
        {"url": "https://www.velasca.com/", "title": "Velasca Milano"},
        {"url": "https://www.boggi.com/it_IT/", "title": "Boggi Milano"},
    ]
    
    state = ProspectorState(
        target_city='Milano',
        target_country='Italy',
        search_results=[
            QuerySearchResults(
                query_index=0,
                query='menswear boutiques milano tailored suits',
                results=[{"url": c["url"], "title": c["title"]} for c in milan_candidates]
            )
        ]
    )
    
    print(f"=== INICIANDO TESTE DE MILÃO (15 BOUTIQUES) ===")
    start_time = time.time()
    
    result = await validation_node(state)
    
    end_time = time.time()
    duration = end_time - start_time
    
    # Process results for the summary
    brands = result.get("potential_brands", [])
    
    # Calculate aggregates (Mocking some values if not directly in result to match user request)
    # In real run, these come from the logs/state
    total_processed = len(milan_candidates)
    extracted_prices = sum(1 for b in brands if b.average_suit_price_usd > 0)
    extracted_stores = sum(1 for b in brands if len(b.store_locations) > 0)
    
    # Print Individual Table
    print("\n| Boutique | Fit Score | Preço (EUR) | Lojas | Status |")
    print("|----------|-----------|-------------|-------|--------|")
    for b in brands:
        price_str = f"€{b.avg_suit_price_eur:.0f}" if b.avg_suit_price_eur else "N/A"
        status = "✅ Selecionada" if b.fit_score > 60 else "⚠️ Baixo Fit"
        print(f"| {b.name[:15]} | {b.fit_score} | {price_str} | {len(b.store_locations)} | {status} |")
    
    # Print Aggregated Summary
    print(f"\n=== MILÃO — RESUMO AGREGADO ===")
    print(f"Total boutiques processadas: {total_processed}")
    # Note: These Z/W values are based on final BrandLeads that passed triage
    print(f"Preços extraídos com sucesso: {extracted_prices}/{len(brands)}")
    print(f"Stores extraídos com sucesso: {extracted_stores}/{len(brands)}")
    print(f"Tempo total de processamento: {int(duration // 60)}m {int(duration % 60)}s")
    
    # Log detailed progress
    print("\n--- PROGRESS LOG ---")
    for p in result.get("progress", []):
        print(p)

if __name__ == "__main__":
    asyncio.run(test_milan_full_run())

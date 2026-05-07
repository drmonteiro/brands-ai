import asyncio
import os
import sys
from dotenv import load_dotenv

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))
load_dotenv(os.path.join(os.path.dirname(__file__), '..', 'backend', '.env'))

from agents.graph import run_prospector_workflow
from models import ProspectorState

async def deploy_validation_lyon():
    print("=== DEPLOY VALIDATION: LYON (10 BOUTIQUES) ===")
    print(f"USE_CRAWL4AI: {os.getenv('USE_CRAWL4AI')}")
    
    # Target 10 boutiques in Lyon
    state = {
        "target_city": "Lyon",
        "target_country": "France",
        "tier": 2,
        "max_candidates": 10,
        "force_refresh": True
    }
    
    # Run the real workflow (Phase 0 -> Phase 1 -> Phase 2)
    final_values, is_interrupted, next_node = await run_prospector_workflow(state)
    
    brands = final_values.get("verified_brands", [])
    print(f"\n✅ PROSPECÇÃO CONCLUÍDA: {len(brands)} marcas verificadas.")
    
    print("\n| Boutique | Price Source | Avg Price | Store Count | Fit Score |")
    print("|----------|--------------|-----------|-------------|-----------|")
    for b in brands:
        price_str = f"€{b.avg_suit_price_eur:.0f}" if b.avg_suit_price_eur else "0"
        print(f"| {b.name[:15]} | {b.price_source or 'none'} | {price_str} | {b.store_count} | {b.fit_score} |")

if __name__ == "__main__":
    asyncio.run(deploy_validation_lyon())

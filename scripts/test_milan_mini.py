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

async def test_milan_mini():
    # 3 Targeted Milanese Boutiques
    mini_candidates = [
        {"url": "https://www.piniparma.com/", "title": "Pini Parma"},     # Expect: css or mixed
        {"url": "https://www.canali.com/it_it/", "title": "Canali"},     # Expect: llm or mixed
        {"url": "https://www.albazar.it/", "title": "Al Bazar"},         # Expect: none
    ]
    
    state = ProspectorState(
        target_city='Milano',
        target_country='Italy',
        search_results=[
            QuerySearchResults(
                query_index=0,
                query='menswear milano',
                results=[{"url": c["url"], "title": c["title"]} for c in mini_candidates]
            )
        ]
    )
    
    print(f"=== MILAN MINI-TEST (3 BOUTIQUES) ===")
    result = await validation_node(state)
    brands = result.get("potential_brands", [])
    
    print("\n| Boutique | Price Source | Avg Price | Price Note | Fit Score |")
    print("|----------|--------------|-----------|------------|-----------|")
    
    # Track which ones were found
    found_urls = [b.website_url for b in brands]
    
    for b in brands:
        price_str = f"€{b.avg_suit_price_eur:.0f}" if b.avg_suit_price_eur else "0"
        source = b.price_source or "none"
        note = (b.price_note or "N/A")[:40]
        print(f"| {b.name[:15]} | {source} | {price_str} | {note} | {b.fit_score} |")
    
    # Handle missing ones (excluded during triage/validation)
    for c in mini_candidates:
        if c["url"] not in found_urls:
             print(f"| {c['title'][:15]} | (Excluded) | - | (Filtered out in triage/validation) | - |")

if __name__ == "__main__":
    asyncio.run(test_milan_mini())

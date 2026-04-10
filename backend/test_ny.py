import asyncio
from models import ProspectorState
from agents.nodes.initializer import initialize_search
from agents.nodes.discovery import discovery_node

async def run_test():
    print("\n--- 1. INITIALIZATION ---")
    state = ProspectorState(
        target_city="New York",
        target_country="USA",
        price_threshold_eur=500,
        candidate_urls=[],
        potential_brands=[],
        verified_brands=[],
        approval_status={},
        email_logs=[],
        search_queries=[],
        progress=[],
        search_results=[]
    )
    
    # We use a dict state for simpler manipulation like in the graph
    state_dict = state.dict()
    state_dict["force_refresh"] = True
    
    init_res = await initialize_search(state_dict)
    state_dict.update(init_res)
    
    print(f"Queries generated: {len(state_dict['search_queries'])}")
    for q in state_dict['search_queries']:
        print(f" - {q}")
        
    print("\n--- 2. TAVILY DISCOVERY ---")
    disc_res = await discovery_node(state_dict)
    candidate_urls = disc_res.get("candidate_urls", [])
    print(f"URLs found from Tavily: {len(candidate_urls)}")
    
    # Just counting the raw outputs
    print("\nTop 20 URLs from Tavily:")
    for url in candidate_urls[:20]:
        print(f" - {url}")

if __name__ == "__main__":
    asyncio.run(run_test())

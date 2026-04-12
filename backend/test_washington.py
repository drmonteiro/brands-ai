import asyncio
from models import ProspectorState
from agents.nodes.initializer import initialize_search
from agents.nodes.discovery import discovery_node
from agents.nodes.validator import validation_node

async def run_test():
    print("\n--- 1. INITIALIZATION ---")
    state = ProspectorState(
        target_city="Washington",
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
    
    state_dict = state.dict()
    state_dict["force_refresh"] = True
    
    init_res = await initialize_search(state_dict)
    state_dict.update(init_res)
    
    print(f"Queries generated: {len(state_dict['search_queries'])}")
        
    print("\n--- 2. TAVILY DISCOVERY ---")
    disc_res = await discovery_node(state_dict)
    state_dict.update(disc_res)
    print(f"URLs found from Tavily: {len(state_dict['candidate_urls'])}")
    
    print("\n--- 3. VALIDATION NODE ---")
    val_res = await validation_node(state_dict)
    state_dict.update(val_res)
    
    print("\n--- PROGRESS LOGS ---")
    for msg in val_res.get("progress", []):
        print(msg)
        
    final_brands = val_res.get("potential_brands", [])
    print(f"\n--- FINAL BRANDS IN WASHINGTON: {len(final_brands)} ---")
    for b in final_brands:
        print(f" - {b.get('name')} | {b.get('headquartersAddress')} | Score: {b.get('fitScore')}")

if __name__ == "__main__":
    asyncio.run(run_test())

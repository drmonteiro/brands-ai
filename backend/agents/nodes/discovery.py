"""
Node 2: Discovery Node
Performs web searches using Tavily and finds potential brand URLs.
"""
from typing import List, Dict, Any, Union
from models import ProspectorState, QuerySearchResults
from .utils import get_tavily_client, normalize_url

async def discovery_node(state: Union[ProspectorState, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Discovery - Find potential brand URLs using REAL web search with Tavily.
    Saves results to the state (replacing legacy global mutable list).
    """
    # Handle state
    search_queries = state.search_queries if hasattr(state, "search_queries") else state.get("search_queries", [])
    
    print("[DISCOVERY] Starting Tavily search...")
    
    candidate_urls: List[str] = []
    unique_urls: set = set()
    search_results: List[QuerySearchResults] = []
    new_progress = []
    
    try:
        total_queries = len(search_queries)
        new_progress.append(f"🔍 Iniciando busca com {total_queries} queries...")
        
        client = get_tavily_client()
        exclude_domains = ["amazon.com", "ebay.com", "walmart.com", "target.com", "nordstrom.com", "yelp.com"]
        
        # Limit to 4 queries (instead of 3) to get more distinct angles,
        # and 40 results per search to reach slightly deeper without hitting full spam territory.
        for i in range(min(total_queries, 4)):
            query = search_queries[i]
            try:
                print(f"[TAVILY] Query {i + 1}: \"{query}\"")
                new_progress.append(f"🔎 Query {i + 1}: \"{query}\"")
                
                response = client.search(
                    query=query,
                    search_depth="advanced",
                    max_results=40,
                    exclude_domains=exclude_domains,
                )
                
                query_results = QuerySearchResults(query_index=i, query=query, results=[])
                for result in response.get("results", []):
                    url = result.get("url", "")
                    if url and normalize_url(url) not in unique_urls:
                        unique_urls.add(normalize_url(url))
                        candidate_urls.append(url)
                        query_results.results.append({
                            "url": url,
                            "title": result.get("title", ""),
                            "content": result.get("content", ""),
                        })
                search_results.append(query_results)
                new_progress.append(f"   ✓ {len(response.get('results', []))} resultados")
            except Exception as e:
                print(f"[TAVILY] Error: {e}")
                new_progress.append(f"   ⚠️ Query {i + 1} falhou")
        
        new_progress.append(f"📈 Encontradas {len(candidate_urls)} URLs únicos")
        print(f"[DISCOVERY] Found {len(candidate_urls)} unique candidate URLs")
        for i, url in enumerate(candidate_urls[:10]):
            print(f"   URL {i+1}: {url}")
        
        return {
            "candidate_urls": candidate_urls,
            "search_results": search_results, # Save to state for validation_node
            "progress": new_progress,
        }
    except Exception as error:
        return {
            "error": str(error),
            "progress": new_progress + ["❌ Descoberta falhou"],
        }

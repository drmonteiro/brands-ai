"""
Calculate Azure OpenAI costs per city search

This script estimates the cost of running a prospect search for one city.
"""

# Azure OpenAI Pricing (as of 2024, approximate - check your Azure portal for exact prices)
# Prices are per 1K tokens

PRICING = {
    # Chat models (GPT-4, GPT-3.5, GPT-5.1)
    "gpt-5.1": {
        "input": 0.005,  # Estimated: $0.005 per 1K input tokens (premium model)
        "output": 0.015,  # Estimated: $0.015 per 1K output tokens
        "note": "⚠️ ESTIMATED - Check Azure portal for exact pricing",
    },
    "gpt-4": {
        "input": 0.03,  # $0.03 per 1K input tokens
        "output": 0.06,  # $0.06 per 1K output tokens
    },
    "gpt-4-turbo": {
        "input": 0.01,  # $0.01 per 1K input tokens
        "output": 0.03,  # $0.03 per 1K output tokens
    },
    "gpt-35-turbo": {  # GPT-3.5 Turbo
        "input": 0.0015,  # $0.0015 per 1K input tokens
        "output": 0.002,  # $0.002 per 1K output tokens
    },
    # Embeddings
    "text-embedding-3-small": {
        "input": 0.02,  # $0.02 per 1M tokens (or $0.00002 per 1K tokens)
    },
}

# Estimated token counts per operation
ESTIMATES = {
    # Query Generation (generate_queries_from_clients)
    "query_generation": {
        "input_tokens": 800,  # Prompt with client info
        "output_tokens": 100,  # JSON array with 3 queries
    },
    
    # Selection Agent (select_best_from_each_query)
    # Processes ~60 results (3 queries × 20 results)
    "selection_agent": {
        "input_tokens": 4000,  # All query results + instructions
        "output_tokens": 500,  # JSON with 10-15 selections
    },
    
    # Final Selection (select_final_candidates)
    # Processes ~10-15 candidates with full content
    "final_selection": {
        "input_tokens": 15000,  # Full website content for 10-15 sites (~12K chars each)
        "output_tokens": 2000,  # JSON with detailed brand info
    },
    
    # Embedding generation (per prospect)
    "embedding_per_prospect": {
        "input_tokens": 150,  # Profile text description
    },
    
    # Similarity Explanation (per prospect)
    "similarity_explanation": {
        "input_tokens": 600,  # Prospect + client comparison
        "output_tokens": 100,  # 2-3 sentence explanation
    },
}

def calculate_cost_per_search(
    model_name: str = "gpt-35-turbo",
    num_prospects: int = 12,  # Average number of prospects found
):
    """
    Calculate total cost for one city search.
    
    Args:
        model_name: LLM model used (gpt-35-turbo, gpt-4, gpt-4-turbo)
        num_prospects: Number of prospects found (typically 10-15)
    """
    model_pricing = PRICING.get(model_name, PRICING["gpt-35-turbo"])
    embedding_pricing = PRICING["text-embedding-3-small"]
    
    costs = {}
    total_cost = 0
    
    # 1. Query Generation (1 call)
    query_gen = ESTIMATES["query_generation"]
    input_cost = (query_gen["input_tokens"] / 1000) * model_pricing["input"]
    output_cost = (query_gen["output_tokens"] / 1000) * model_pricing["output"]
    query_gen_cost = input_cost + output_cost
    costs["Query Generation"] = query_gen_cost
    total_cost += query_gen_cost
    
    # 2. Selection Agent (1 call)
    selection = ESTIMATES["selection_agent"]
    input_cost = (selection["input_tokens"] / 1000) * model_pricing["input"]
    output_cost = (selection["output_tokens"] / 1000) * model_pricing["output"]
    selection_cost = input_cost + output_cost
    costs["Selection Agent"] = selection_cost
    total_cost += selection_cost
    
    # 3. Final Selection (1 call)
    final = ESTIMATES["final_selection"]
    input_cost = (final["input_tokens"] / 1000) * model_pricing["input"]
    output_cost = (final["output_tokens"] / 1000) * model_pricing["output"]
    final_cost = input_cost + output_cost
    costs["Final Selection"] = final_cost
    total_cost += final_cost
    
    # 4. Embeddings (num_prospects calls)
    embedding = ESTIMATES["embedding_per_prospect"]
    # Note: embeddings are priced per 1M tokens, so divide by 1000
    embedding_cost_per = (embedding["input_tokens"] / 1000000) * embedding_pricing["input"]
    total_embedding_cost = embedding_cost_per * num_prospects
    costs[f"Embeddings ({num_prospects} prospects)"] = total_embedding_cost
    total_cost += total_embedding_cost
    
    # 5. Similarity Explanations (num_prospects calls)
    explanation = ESTIMATES["similarity_explanation"]
    input_cost_per = (explanation["input_tokens"] / 1000) * model_pricing["input"]
    output_cost_per = (explanation["output_tokens"] / 1000) * model_pricing["output"]
    explanation_cost_per = input_cost_per + output_cost_per
    total_explanation_cost = explanation_cost_per * num_prospects
    costs[f"Similarity Explanations ({num_prospects} prospects)"] = total_explanation_cost
    total_cost += total_explanation_cost
    
    return costs, total_cost


if __name__ == "__main__":
    print("=" * 70)
    print("Azure OpenAI Cost Calculator - Per City Search")
    print("=" * 70)
    
    print("\n📊 COST BREAKDOWN (GPT-3.5 Turbo):")
    print("-" * 70)
    costs_gpt35, total_gpt35 = calculate_cost_per_search("gpt-35-turbo", num_prospects=12)
    for operation, cost in costs_gpt35.items():
        print(f"  {operation:40} ${cost:.4f}")
    print(f"\n  {'TOTAL PER SEARCH':40} ${total_gpt35:.4f}")
    print(f"  {'TOTAL PER 10 SEARCHES':40} ${total_gpt35 * 10:.4f}")
    print(f"  {'TOTAL PER 100 SEARCHES':40} ${total_gpt35 * 100:.4f}")
    
    print("\n📊 COST BREAKDOWN (GPT-4 Turbo):")
    print("-" * 70)
    costs_gpt4, total_gpt4 = calculate_cost_per_search("gpt-4-turbo", num_prospects=12)
    for operation, cost in costs_gpt4.items():
        print(f"  {operation:40} ${cost:.4f}")
    print(f"\n  {'TOTAL PER SEARCH':40} ${total_gpt4:.4f}")
    print(f"  {'TOTAL PER 10 SEARCHES':40} ${total_gpt4 * 10:.4f}")
    print(f"  {'TOTAL PER 100 SEARCHES':40} ${total_gpt4 * 100:.4f}")
    
    print("\n📊 COST BREAKDOWN (GPT-4):")
    print("-" * 70)
    costs_gpt4_std, total_gpt4_std = calculate_cost_per_search("gpt-4", num_prospects=12)
    for operation, cost in costs_gpt4_std.items():
        print(f"  {operation:40} ${cost:.4f}")
    print(f"\n  {'TOTAL PER SEARCH':40} ${total_gpt4_std:.4f}")
    print(f"  {'TOTAL PER 10 SEARCHES':40} ${total_gpt4_std * 10:.4f}")
    print(f"  {'TOTAL PER 100 SEARCHES':40} ${total_gpt4_std * 100:.4f}")
    
    print("\n📊 COST BREAKDOWN (GPT-5.1) - YOUR CURRENT MODEL:")
    print("-" * 70)
    costs_gpt51, total_gpt51 = calculate_cost_per_search("gpt-5.1", num_prospects=12)
    for operation, cost in costs_gpt51.items():
        print(f"  {operation:40} ${cost:.4f}")
    print(f"\n  {'TOTAL PER SEARCH':40} ${total_gpt51:.4f}")
    print(f"  {'TOTAL PER 10 SEARCHES':40} ${total_gpt51 * 10:.4f}")
    print(f"  {'TOTAL PER 100 SEARCHES':40} ${total_gpt51 * 100:.4f}")
    print(f"\n  ⚠️  Preços estimados - verifica no Azure Portal para valores exatos")
    
    print("\n" + "=" * 70)
    print("💡 NOTES:")
    print("  - Prices are approximate and may vary by Azure region")
    print("  - Check your Azure portal for exact pricing")
    print("  - Embeddings are very cheap ($0.02 per 1M tokens)")
    print("  - Most cost comes from LLM calls (ChatGPT)")
    print("  - Similarity explanations add ~$0.01-0.02 per prospect")
    print("=" * 70)
    
    print("\n📈 COST OPTIMIZATION TIPS:")
    print("  1. Use GPT-3.5 Turbo instead of GPT-4 (10x cheaper)")
    print("  2. Reduce number of prospects processed (currently ~12)")
    print("  3. Skip similarity explanations for low-scoring prospects")
    print("  4. Cache embeddings if reprocessing same prospects")
    print("=" * 70)

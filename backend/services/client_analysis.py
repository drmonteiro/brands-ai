"""
Client Analysis Service
Analyzes existing Lança clients to generate high-quality examples for the LLM.
"""
from typing import List
from data.lanca_clients import LANCA_CLIENTS

def generate_rich_client_examples(n_examples: int = 5) -> str:
    """
    Generate rich examples from REAL Lança clients for LLM prompts.
    This helps the LLM understand EXACTLY what a good client looks like.
    """
    total_clients = len(LANCA_CLIENTS)
    
    # Calculate stats
    store_counts = [c.get('store_count', 0) for c in LANCA_CLIENTS if c.get('store_count')]
    avg_stores = sum(store_counts) / len(store_counts) if store_counts else 0
    min_stores = min(store_counts) if store_counts else 0
    max_stores = max(store_counts) if store_counts else 0
    
    prices = [c.get('pvp_suits_eur', 0) for c in LANCA_CLIENTS if c.get('pvp_suits_eur') and isinstance(c.get('pvp_suits_eur'), (int, float))]
    avg_price = sum(prices) / len(prices) if prices else 0
    min_price = min(prices) if prices else 0
    max_price = max(prices) if prices else 0
    
    mtm_count = sum(1 for c in LANCA_CLIENTS if c.get('made_to_measure'))
    wool_100_count = sum(1 for c in LANCA_CLIENTS if c.get('wool_percentage') == '100%')
    
    years = [c.get('years_as_client', 0) for c in LANCA_CLIENTS if c.get('years_as_client')]
    avg_years = sum(years) / len(years) if years else 0
    
    general_summary = f"""
📊 PERFIL GERAL DOS {total_clients} CLIENTES LANÇA:
   • Lojas: {min_stores}-{max_stores} (média: {avg_stores:.0f})
   • Preço fatos: €{min_price:.0f}-€{max_price:.0f} (média: €{avg_price:.0f})
   • Made-to-measure: {mtm_count}/{total_clients} oferecem
   • 100% Lã: {wool_100_count}/{total_clients} utilizam
   • Tempo médio como cliente: {avg_years:.0f} anos
"""
    
    tier_priority = {"high_value": 0, "medium_value": 1, "low_value": 2}
    sorted_clients = sorted(
        LANCA_CLIENTS,
        key=lambda c: (tier_priority.get(c.get("tier", "low_value"), 2), -c.get("years_as_client", 0))
    )
    
    top_clients = sorted_clients[:n_examples]
    examples = []
    for c in top_clients:
        price_str = f"€{c.get('pvp_suits_eur', 'unknown')}" if c.get('pvp_suits_eur') else "N/A"
        mtm_str = "Sim" if c.get('made_to_measure') else "Não"
        examples.append(f"""
✅ CLIENTE REAL: {c['name']} ({c['country']})
   • Lojas: {c.get('store_count', 'unknown')} | Preço: {price_str} | MTM: {mtm_str}
   • PORQUÊ FUNCIONA: {c.get('description', '')}""")
    
    avoid = """
❌ EVITAR: Grandes cadeias (50+ lojas), Fast fashion (<€200), Só online, Grandes Armazéns."""
    
    return general_summary + "\n".join(examples) + "\n" + avoid

"""
Client Analysis Service
Analyzes existing Lança clients to generate high-quality examples for the LLM.
Covers 3 product categories: complete suits, jackets only, and trousers only.
"""
from typing import List
from data.lanca_clients import LANCA_CLIENTS

def generate_rich_client_examples(n_examples: int = 5) -> str:
    """
    Generate rich examples from REAL Lança clients for LLM prompts.
    This helps the LLM understand EXACTLY what a good client looks like.
    Includes 3-category price ranges (suits, jackets, trousers).
    """
    total_clients = len(LANCA_CLIENTS)
    
    # Calculate stats — Suits
    store_counts = [c.get('store_count', 0) for c in LANCA_CLIENTS if c.get('store_count')]
    avg_stores = sum(store_counts) / len(store_counts) if store_counts else 0
    min_stores = min(store_counts) if store_counts else 0
    max_stores = max(store_counts) if store_counts else 0
    
    suit_prices = [c.get('pvp_suits_eur', 0) for c in LANCA_CLIENTS if c.get('pvp_suits_eur') and isinstance(c.get('pvp_suits_eur'), (int, float))]
    avg_suit_price = sum(suit_prices) / len(suit_prices) if suit_prices else 0
    min_suit_price = min(suit_prices) if suit_prices else 0
    max_suit_price = max(suit_prices) if suit_prices else 0
    
    # Calculate stats — Jackets
    jacket_prices = [c.get('pvp_jacket_eur', 0) for c in LANCA_CLIENTS if c.get('pvp_jacket_eur') and isinstance(c.get('pvp_jacket_eur'), (int, float))]
    avg_jacket_price = sum(jacket_prices) / len(jacket_prices) if jacket_prices else 0
    min_jacket_price = min(jacket_prices) if jacket_prices else 0
    max_jacket_price = max(jacket_prices) if jacket_prices else 0
    
    # Calculate stats — Trousers
    trouser_prices = [c.get('pvp_trousers_eur', 0) for c in LANCA_CLIENTS if c.get('pvp_trousers_eur') and isinstance(c.get('pvp_trousers_eur'), (int, float))]
    avg_trouser_price = sum(trouser_prices) / len(trouser_prices) if trouser_prices else 0
    min_trouser_price = min(trouser_prices) if trouser_prices else 0
    max_trouser_price = max(trouser_prices) if trouser_prices else 0
    
    mtm_count = sum(1 for c in LANCA_CLIENTS if c.get('made_to_measure'))
    wool_100_count = sum(1 for c in LANCA_CLIENTS if c.get('wool_percentage') == '100%')
    
    years = [c.get('years_as_client', 0) for c in LANCA_CLIENTS if c.get('years_as_client')]
    avg_years = sum(years) / len(years) if years else 0
    
    general_summary = f"""
📊 PERFIL GERAL DOS {total_clients} CLIENTES LANÇA:
   • Lojas: {min_stores}-{max_stores} (média: {avg_stores:.0f})
   • Preço fatos completos: €{min_suit_price:.0f}-€{max_suit_price:.0f} (média: €{avg_suit_price:.0f})
   • Preço só casaco: €{min_jacket_price:.0f}-€{max_jacket_price:.0f} (média: €{avg_jacket_price:.0f})
   • Preço só calça: €{min_trouser_price:.0f}-€{max_trouser_price:.0f} (média: €{avg_trouser_price:.0f})
   • Made-to-measure: {mtm_count}/{total_clients} oferecem
   • 100% Lã: {wool_100_count}/{total_clients} utilizam
   • Tempo médio como cliente: {avg_years:.0f} anos

🎯 GAMAS DE PREÇO ALVO LANÇA:
   • Fato completo (casaco + calça): €500 – €1.700
   • Só casaco: €300 – €1.000
   • Só calça: €250 – €750
"""
    
    tier_priority = {"high_value": 0, "medium_value": 1, "low_value": 2}
    sorted_clients = sorted(
        LANCA_CLIENTS,
        key=lambda c: (tier_priority.get(c.get("tier", "low_value"), 2), -c.get("years_as_client", 0))
    )
    
    top_clients = sorted_clients[:n_examples]
    examples = []
    for c in top_clients:
        suit_str = f"€{c.get('pvp_suits_eur', 'unknown')}" if c.get('pvp_suits_eur') else "N/A"
        jacket_str = f"€{c.get('pvp_jacket_eur', 'unknown')}" if c.get('pvp_jacket_eur') else "N/A"
        trouser_str = f"€{c.get('pvp_trousers_eur', 'unknown')}" if c.get('pvp_trousers_eur') else "N/A"
        mtm_str = "Sim" if c.get('made_to_measure') else "Não"
        examples.append(f"""
✅ CLIENTE REAL: {c['name']} ({c['country']})
   • Lojas: {c.get('store_count', 'unknown')} | Fato: {suit_str} | Casaco: {jacket_str} | Calça: {trouser_str} | MTM: {mtm_str}
   • PORQUÊ FUNCIONA: {c.get('description', '')}""")
    
    avoid = """
❌ EVITAR: Grandes cadeias (50+ lojas), Fast fashion (<€250 casacos, <€175 calças), Só online, Grandes Armazéns, Marcas sem sede na cidade."""
    
    return general_summary + "\n".join(examples) + "\n" + avoid

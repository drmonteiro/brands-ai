"""
Confeções Lança - Top 18 Priority Clients Database

Esta base de dados contém APENAS os 18 clientes mais importantes da Lança,
com dados detalhados para criar embeddings de alta qualidade e definir
o perfil ideal de cliente para prospecção.
"""

from typing import List, Dict, Literal

# ============================================================================
# LANÇA TOP 18 CLIENTS DATABASE
# ============================================================================

LANCA_CLIENTS: List[Dict] = [
    # ========== 1. Hawes & Curtis ==========
    {
        "name": "Hawes & Curtis",
        "brand_name": "Hawes & Curtis",
        "country": "UK",
        "country_code": "GB",
        "city": "London",
        "years_as_client": 10,  # Aproximado
        "store_count": 30,
        "avg_suit_price_eur": "500",
        "pvp_suits_eur": 500,
        "wool_percentage": "100%",
        "made_to_measure": False,
        "brand_type": "own_brand",
        "brand_style": "Heritage/Premium",
        "business_model": "Retail",
        "tier": "high_value",
        "notes": "Melhor cliente em faturação, mas margem não muito boa atualmente",
        "description": "British heritage menswear brand known for shirts and suits. Top revenue client for Lança.",
    },
    
    # ========== 2. Carlos Nieto ==========
    {
        "name": "Carlos Nieto",
        "brand_name": "Carlos Nieto",
        "country": "Colombia",
        "country_code": "CO",
        "city": "Bogotá",
        "years_as_client": 12,
        "store_count": 20,
        "avg_suit_price_eur": "800",
        "pvp_suits_eur": 800,
        "wool_percentage": "100%",
        "made_to_measure": True,
        "brand_type": "own_brand",
        "brand_style": "Premium",
        "business_model": "Retail",
        "tier": "high_value",
        "notes": "Cliente há 12 anos, 20 lojas em Bogotá",
        "description": "Premium Colombian menswear brand with 20 stores, 12-year partnership with Lança.",
    },
    
    # ========== 3. Bayertree Favourbrook ==========
    {
        "name": "Bayertree Favourbrook",
        "brand_name": "Favourbrook & Oliver Spencer",
        "country": "UK",
        "country_code": "GB",
        "city": "London",
        "years_as_client": 10,
        "store_count": 8,
        "avg_suit_price_eur": "1000",
        "pvp_suits_eur": 1000,
        "wool_percentage": "100%",
        "made_to_measure": True,
        "brand_type": "own_brand",
        "brand_style": "Luxury/Bespoke",
        "business_model": "Bespoke/Retail",
        "tier": "high_value",
        "notes": "Comercializa Favourbrook e Oliver Spencer",
        "description": "British luxury occasion wear and bespoke tailoring, 10-year partnership.",
    },
    
    # ========== 4. Wickett Jones ==========
    {
        "name": "Wickett Jones",
        "brand_name": "Wickett Jones",
        "country": "Portugal",
        "country_code": "PT",
        "city": "Lisboa",
        "years_as_client": 10,
        "store_count": 3,  # 2 lojas + espaço no El Corte Inglés
        "avg_suit_price_eur": "600",
        "pvp_suits_eur": 600,
        "wool_percentage": "100%",
        "made_to_measure": True,
        "brand_type": "own_brand",
        "brand_style": "Premium",
        "business_model": "Retail",
        "tier": "high_value",
        "notes": "2 lojas em Lisboa + espaço no El Corte Inglés de Lisboa e Gaia",
        "description": "Portuguese premium menswear brand with stores in Lisbon and El Corte Inglés presence.",
    },
    
    # ========== 5. Martin Sturm GMBH ==========
    {
        "name": "Martin Sturm GMBH",
        "brand_name": "Sturm",
        "country": "Austria",
        "country_code": "AT",
        "city": "Vienna",
        "years_as_client": 5,
        "store_count": 1,
        "avg_suit_price_eur": "1500",
        "pvp_suits_eur": 1500,
        "wool_percentage": "100%",
        "made_to_measure": True,
        "brand_type": "multibrand",
        "brand_style": "Luxury/Premium",
        "business_model": "Retail",
        "tier": "high_value",
        "notes": "Loja multimarca de luxo em Viena",
        "description": "Austrian luxury multi-brand retailer in Vienna with premium pricing.",
    },
    
    # ========== 6. Grupo YES ==========
    {
        "name": "Grupo YES",
        "brand_name": "Adolfo Dominguez",
        "country": "Peru",
        "country_code": "PE",
        "city": "Lima",
        "years_as_client": 7,
        "store_count": 29,
        "avg_suit_price_eur": "unknown",
        "pvp_suits_eur": None,
        "wool_percentage": "100%",
        "made_to_measure": False,
        "brand_type": "multibrand",
        "brand_style": "Premium/Multi-brand",
        "business_model": "Retail/Distribution",
        "tier": "high_value",
        "notes": "Distribui Adolfo Dominguez no Peru, 29 lojas",
        "description": "Peruvian multi-brand retailer distributing Adolfo Dominguez with 29 stores.",
    },
    
    # ========== 7. Sastrerías Españolas ==========
    {
        "name": "Sastrerías Españolas",
        "brand_name": "Jajoan",
        "country": "Spain",
        "country_code": "ES",
        "city": "Spain",  # Múltiplas cidades
        "years_as_client": 7,
        "store_count": 6,
        "avg_suit_price_eur": "375",
        "pvp_suits_eur": 375,
        "wool_percentage": "100%",
        "made_to_measure": True,
        "brand_type": "own_brand",
        "brand_style": "Traditional/Bespoke",
        "business_model": "Retail/Bespoke",
        "tier": "medium_value",
        "notes": "Marca jajoan, PVP a partir de 375€",
        "description": "Spanish tailoring company with 6 stores and accessible premium pricing.",
    },
    
    # ========== 8. Walker Slater ==========
    {
        "name": "Walker Slater",
        "brand_name": "Walker Slater",
        "country": "UK",
        "country_code": "GB",
        "city": "Edinburgh",
        "years_as_client": 5,
        "store_count": 5,
        "avg_suit_price_eur": "800",
        "pvp_suits_eur": 800,
        "wool_percentage": "100%",
        "made_to_measure": True,
        "brand_type": "own_brand",
        "brand_style": "Heritage/Scottish",
        "business_model": "Retail/Bespoke",
        "tier": "medium_value",
        "notes": "Especialista em tweed escocês",
        "description": "Scottish heritage tweed and suits specialist with 5 stores in Edinburgh.",
    },
    
    # ========== 9. Brigdens ==========
    {
        "name": "Brigdens",
        "brand_name": "Brigdens",
        "country": "UK",
        "country_code": "GB",
        "city": "Derby",
        "years_as_client": 10,
        "store_count": 2,
        "avg_suit_price_eur": "800",
        "pvp_suits_eur": 800,
        "wool_percentage": "100%",
        "made_to_measure": True,
        "brand_type": "multibrand",
        "brand_style": "Premium",
        "business_model": "Retail",
        "tier": "medium_value",
        "notes": "Loja multimarca em Derby",
        "description": "UK multi-brand retailer in Derby with 10-year partnership and 2 stores.",
    },
    
    # ========== 10. Gresham Blake ==========
    {
        "name": "Gresham Blake",
        "brand_name": "Gresham Blake",
        "country": "UK",
        "country_code": "GB",
        "city": "Brighton",
        "years_as_client": 10,
        "store_count": 1,
        "avg_suit_price_eur": "1000",
        "pvp_suits_eur": 1000,
        "wool_percentage": "100%",
        "made_to_measure": True,
        "brand_type": "own_brand",
        "brand_style": "Bespoke/Contemporary",
        "business_model": "Bespoke",
        "tier": "medium_value",
        "notes": "Alfaiate bespoke em Brighton",
        "description": "British bespoke tailor in Brighton with 10-year partnership and luxury positioning.",
    },
    
    # ========== 11. Fernando de Carcer ==========
    {
        "name": "Fernando de Carcer",
        "brand_name": "Fernando de Carcer",
        "country": "Spain",
        "country_code": "ES",
        "city": "Madrid",
        "years_as_client": 3,  # 2-3 anos
        "store_count": 1,
        "avg_suit_price_eur": "600",
        "pvp_suits_eur": 600,
        "wool_percentage": "100%",
        "made_to_measure": True,
        "brand_type": "own_brand",
        "brand_style": "Premium/Spanish",
        "business_model": "Retail",
        "tier": "low_value",
        "notes": "Cliente recente, marca própria em Madrid",
        "description": "Spanish premium menswear brand in Madrid with own brand focus.",
    },
    
    # ========== 12. Original Fivers (Flax London) ==========
    {
        "name": "Original Fivers",
        "brand_name": "Flax London",
        "country": "UK",
        "country_code": "GB",
        "city": "London",
        "years_as_client": 3,
        "store_count": 2,
        "avg_suit_price_eur": "800",
        "pvp_suits_eur": 800,
        "wool_percentage": "100%",
        "made_to_measure": True,
        "brand_type": "own_brand",
        "brand_style": "Contemporary/Premium",
        "business_model": "Retail",
        "tier": "low_value",
        "notes": "Marca Flax London",
        "description": "London-based contemporary menswear brand with 2 stores and premium positioning.",
    },
    
    # ========== 13. Trotter & Dean ==========
    {
        "name": "Trotter & Dean",
        "brand_name": "Trotter & Dean",
        "country": "UK",
        "country_code": "GB",
        "city": "Cambridge",
        "years_as_client": 2,
        "store_count": 5,
        "avg_suit_price_eur": "1000",
        "pvp_suits_eur": 1000,
        "wool_percentage": "100%",
        "made_to_measure": True,
        "brand_type": "own_brand",
        "brand_style": "Heritage/Premium",
        "business_model": "Retail",
        "tier": "low_value",
        "notes": "Cliente recente com 5 lojas em Cambridge",
        "description": "British heritage menswear brand in Cambridge with 5 stores and luxury pricing.",
    },
    
    # ========== 14. Garcia Madrid ==========
    {
        "name": "Garcia Madrid",
        "brand_name": "Garcia Madrid",
        "country": "Spain",
        "country_code": "ES",
        "city": "Madrid",
        "years_as_client": 10,
        "store_count": 1,
        "avg_suit_price_eur": "1000",
        "pvp_suits_eur": 1000,
        "wool_percentage": "100%",
        "made_to_measure": True,
        "brand_type": "own_brand",
        "brand_style": "Premium/Spanish",
        "business_model": "Retail",
        "tier": "low_value",
        "notes": "Parceria de 10 anos, boutique única em Madrid",
        "description": "Spanish premium menswear brand in Madrid with 10-year partnership.",
    },
    
    # ========== 15. Progress Dealer ==========
    {
        "name": "Progress Dealer",
        "brand_name": "Dealer",
        "country": "Angola",
        "country_code": "AO",
        "city": "Luanda",
        "years_as_client": 7,
        "store_count": 2,
        "avg_suit_price_eur": "1000",
        "pvp_suits_eur": 1000,
        "wool_percentage": "100%",
        "made_to_measure": False,
        "brand_type": "own_brand",
        "brand_style": "Premium/African",
        "business_model": "Retail",
        "tier": "medium_value",
        "notes": "2 lojas em Luanda, mercado angolano",
        "description": "Angolan premium menswear brand with 2 stores in Luanda.",
    },
    
    # ========== 16. Vila Verdi ==========
    {
        "name": "Vila Verdi",
        "brand_name": "Vila Verdi",
        "country": "Belgium",
        "country_code": "BE",
        "city": "Ghent",
        "years_as_client": 10,
        "store_count": 1,
        "avg_suit_price_eur": "800",
        "pvp_suits_eur": 800,
        "wool_percentage": "100%",
        "made_to_measure": True,
        "brand_type": "own_brand",
        "brand_style": "Bespoke/Premium",
        "business_model": "Bespoke",
        "tier": "medium_value",
        "notes": "Só faz por medida, boutique em Ghent",
        "description": "Belgian bespoke-only tailor in Ghent with 10-year exclusive partnership.",
    },
    
    # ========== 17. Supaman (Oliver Brown) ==========
    {
        "name": "Supaman",
        "brand_name": "Oliver Brown",
        "country": "UK",
        "country_code": "GB",
        "city": "London",
        "years_as_client": 10,
        "store_count": 5,
        "avg_suit_price_eur": "1000",
        "pvp_suits_eur": 1000,
        "wool_percentage": "100%",
        "made_to_measure": True,
        "brand_type": "own_brand",
        "brand_style": "Luxury/Heritage",
        "business_model": "Retail",
        "tier": "medium_value",
        "notes": "Marca Oliver Brown, 5 lojas em Londres",
        "description": "British luxury heritage menswear brand Oliver Brown with 5 London stores.",
    },
    
    # ========== 18. Coshile (Anthony's London) ==========
    {
        "name": "Coshile",
        "brand_name": "Anthony's London",
        "country": "Czech Republic",
        "country_code": "CZ",
        "city": "Prague",
        "years_as_client": 6,
        "store_count": 8,
        "avg_suit_price_eur": "750",
        "pvp_suits_eur": 750,
        "wool_percentage": "100%",
        "made_to_measure": False,
        "brand_type": "own_brand",
        "brand_style": "Premium/Contemporary",
        "business_model": "Retail",
        "tier": "medium_value",
        "notes": "Marca Anthony's London, 8 lojas na República Checa",
        "description": "Czech retailer with Anthony's London brand and 8 stores across Czech Republic.",
    },
]


# ============================================================================
# IDEAL CLIENT PROFILE (based on top 18 analysis)
# ============================================================================

IDEAL_CLIENT_PROFILE = {
    "avg_years_as_client": 7.5,
    "avg_store_count": 6,
    "avg_pvp_eur": 850,
    "preferred_brand_type": "own_brand",  # 78% dos top 18 são marca própria
    "preferred_business_model": "Retail",
    "characteristics": [
        "Small to medium boutique (1-20 stores)",
        "Premium pricing (€500-€1500 per suit)",
        "Long-term partnership oriented (5+ years)",
        "Own brand focus (not multi-brand)",
        "Made-to-measure capability preferred",
        "100% wool suits",
        "European or Americas market",
    ],
    "search_price_thresholds": {
        "europe": 400,      # Pesquisar a partir de 400€
        "usa": 600,         # Mercado EUA, pesquisar a partir de 600€
        "latam": 350,       # América Latina, ajustado ao mercado
    }
}


# ============================================================================
# MARKET STRENGTH BY COUNTRY (based on top 18 clients)
# ============================================================================

def calculate_market_strength() -> Dict[str, float]:
    """Calculate market strength percentage by country based on client count"""
    country_count: Dict[str, int] = {}
    
    for client in LANCA_CLIENTS:
        country = client["country_code"]
        if country not in country_count:
            country_count[country] = 0
        country_count[country] += 1
    
    total = len(LANCA_CLIENTS)
    return {
        country: (count / total) * 100
        for country, count in country_count.items()
    }


MARKET_STRENGTH = calculate_market_strength()

# Pre-calculated for quick access
MARKET_STRENGTH_STATIC = {
    "GB": 44.4,   # UK - 8 clients (strongest market)
    "ES": 16.7,   # Spain - 3 clients
    "CO": 5.6,    # Colombia - 1 client (but high value)
    "PT": 5.6,    # Portugal - 1 client
    "AT": 5.6,    # Austria - 1 client
    "PE": 5.6,    # Peru - 1 client
    "BE": 5.6,    # Belgium - 1 client
    "AO": 5.6,    # Angola - 1 client
    "CZ": 5.6,    # Czech Republic - 1 client
}


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_clients_by_tier(tier: Literal["high_value", "medium_value", "low_value"]) -> List[Dict]:
    """Get clients filtered by tier"""
    return [c for c in LANCA_CLIENTS if c["tier"] == tier]


def get_clients_by_country(country_code: str) -> List[Dict]:
    """Get clients filtered by country"""
    return [c for c in LANCA_CLIENTS if c["country_code"] == country_code]


def get_market_strength(country_code: str) -> float:
    """Get market strength for a country (0-100)"""
    return MARKET_STRENGTH_STATIC.get(country_code, 0.0)


def get_top_clients(n: int = 10) -> List[Dict]:
    """Get top N clients by years as client (loyalty)"""
    sorted_clients = sorted(LANCA_CLIENTS, key=lambda x: x.get("years_as_client", 0), reverse=True)
    return sorted_clients[:n]


def get_clients_by_brand_type(brand_type: Literal["own_brand", "multibrand"]) -> List[Dict]:
    """Get clients filtered by brand type"""
    return [c for c in LANCA_CLIENTS if c.get("brand_type") == brand_type]


def get_long_term_clients(min_years: int = 5) -> List[Dict]:
    """Get clients with at least min_years of partnership"""
    return [c for c in LANCA_CLIENTS if c.get("years_as_client", 0) >= min_years]


# ============================================================================
# SUMMARY STATS
# ============================================================================

TOTAL_CLIENTS = len(LANCA_CLIENTS)
HIGH_VALUE_CLIENTS = len(get_clients_by_tier("high_value"))
MEDIUM_VALUE_CLIENTS = len(get_clients_by_tier("medium_value"))
LOW_VALUE_CLIENTS = len(get_clients_by_tier("low_value"))
OWN_BRAND_CLIENTS = len(get_clients_by_brand_type("own_brand"))
MULTIBRAND_CLIENTS = len(get_clients_by_brand_type("multibrand"))
LONG_TERM_CLIENTS = len(get_long_term_clients(5))

if __name__ == "__main__":
    print(f"=== Lança Top 18 Clients Database ===")
    print(f"Total Clients: {TOTAL_CLIENTS}")
    print(f"High Value: {HIGH_VALUE_CLIENTS}")
    print(f"Medium Value: {MEDIUM_VALUE_CLIENTS}")
    print(f"Low Value: {LOW_VALUE_CLIENTS}")
    print(f"\nBrand Type:")
    print(f"  Own Brand: {OWN_BRAND_CLIENTS} ({OWN_BRAND_CLIENTS/TOTAL_CLIENTS*100:.1f}%)")
    print(f"  Multi-brand: {MULTIBRAND_CLIENTS} ({MULTIBRAND_CLIENTS/TOTAL_CLIENTS*100:.1f}%)")
    print(f"\nLong-term Clients (5+ years): {LONG_TERM_CLIENTS}")
    print(f"\nMarket Strength by Country:")
    for country, strength in sorted(MARKET_STRENGTH_STATIC.items(), key=lambda x: x[1], reverse=True):
        print(f"  {country}: {strength:.1f}%")
    print(f"\nIdeal Client Profile:")
    for key, value in IDEAL_CLIENT_PROFILE.items():
        print(f"  {key}: {value}")

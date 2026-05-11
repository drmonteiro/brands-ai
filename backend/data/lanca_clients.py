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
        "pvp_jacket_eur": 300,
        "pvp_trousers_eur": 250,
        "wool_percentage": "100%",
        "made_to_measure": False,
        "brand_type": "own_brand",
        "brand_style": "Heritage/Premium",
        "business_model": "Retail",
        "tier": "high_value",
        "notes": "Melhor cliente em faturação, mas margem não muito boa atualmente",
        "description": "British heritage menswear brand established in Jermyn Street, London, known for premium shirts, suits and formal wear. Style is classic British tailoring with a modern edge — structured shoulders, clean silhouettes, and natural fabrics. Suits retail from £400-£600 (€500), jackets £250-£350 (€300), trousers £200-£280 (€250). Retail business model with 30 stores across the UK. Target customer is the professional man who wants quality tailoring at an accessible premium price point. Top revenue client for Lança, 10-year manufacturing partnership.",
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
        "pvp_jacket_eur": 500,
        "pvp_trousers_eur": 350,
        "wool_percentage": "100%",
        "made_to_measure": True,
        "brand_type": "own_brand",
        "brand_style": "Premium",
        "business_model": "Retail",
        "tier": "high_value",
        "notes": "Cliente há 12 anos, 20 lojas em Bogotá",
        "description": "Premium Colombian menswear brand headquartered in Bogotá, specialising in tailored suits, blazers and trousers for the Latin American market. Classic-contemporary style with European-influenced silhouettes and 100% wool fabrics. Suits retail at approximately $900 USD (€800), jackets $560 (€500), trousers $390 (€350). Operates 20 retail stores across Colombia with both ready-to-wear and made-to-measure offering. Target customer is the Colombian professional and executive. 12-year manufacturing partnership with Lança — one of the longest-standing clients.",
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
        "pvp_jacket_eur": 650,
        "pvp_trousers_eur": 450,
        "wool_percentage": "100%",
        "made_to_measure": True,
        "brand_type": "own_brand",
        "brand_style": "Luxury/Bespoke",
        "business_model": "Bespoke/Retail",
        "tier": "high_value",
        "notes": "Comercializa Favourbrook e Oliver Spencer",
        "description": "British luxury occasion wear and bespoke tailoring group based in London. Bayertree distributes Favourbrook (colourful waistcoats, occasion suits, wedding wear) and Oliver Spencer (contemporary relaxed tailoring). Rich fabrics, silk linings, bold patterns alongside classic cuts. Suits from £800-£1200 (€1000), jackets £500-£750 (€650), trousers £350-£500 (€450). Retail and bespoke business model with 8 locations. Target customer is the discerning man seeking distinctive occasion wear and luxury everyday tailoring. 10-year partnership with Lança.",
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
        "pvp_jacket_eur": 380,
        "pvp_trousers_eur": 280,
        "wool_percentage": "100%",
        "made_to_measure": True,
        "brand_type": "own_brand",
        "brand_style": "Premium",
        "business_model": "Retail",
        "tier": "high_value",
        "notes": "2 lojas em Lisboa + espaço no El Corte Inglés de Lisboa e Gaia",
        "description": "Portuguese premium menswear brand headquartered in Lisbon. Classic European tailoring with a focus on quality wool suits, jackets and trousers at accessible premium prices. Suits from €600, jackets €380, trousers €280. Retail model with 2 dedicated stores in Lisbon plus concessions at El Corte Inglés (Lisbon and Vila Nova de Gaia). Made-to-measure service available. Target customer is the Portuguese professional seeking quality own-brand tailoring. 10-year partnership with Lança.",
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
        "pvp_jacket_eur": 950,
        "pvp_trousers_eur": 700,
        "wool_percentage": "100%",
        "made_to_measure": True,
        "brand_type": "multibrand",
        "brand_style": "Luxury/Premium",
        "business_model": "Retail",
        "tier": "high_value",
        "notes": "Loja multimarca de luxo em Viena",
        "description": "Austrian luxury multi-brand menswear retailer located in Vienna. Curates high-end European suits, jackets and formal wear with impeccable attention to fabric and fit. Suits retail from €1500, jackets €950, trousers €700 — positioning at the upper end of the premium range. Single boutique with made-to-measure consultations. Target customer is the Viennese executive and luxury buyer seeking world-class tailoring. 5-year partnership with Lança for 100% wool garments.",
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
        "pvp_jacket_eur": None,
        "pvp_trousers_eur": None,
        "wool_percentage": "100%",
        "made_to_measure": False,
        "brand_type": "multibrand",
        "brand_style": "Premium/Multi-brand",
        "business_model": "Retail/Distribution",
        "tier": "high_value",
        "notes": "Distribui Adolfo Dominguez no Peru, 29 lojas",
        "description": "Peruvian multi-brand retail group based in Lima, distributing Adolfo Dominguez and other European fashion brands across Peru. Operates 29 retail stores nationally — one of the largest distribution networks among Lança clients. Style is premium European menswear adapted for the Latin American market. 100% wool suits manufactured by Lança. Target customer is the Peruvian professional and fashion-conscious man. 7-year distribution partnership.",
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
        "pvp_jacket_eur": 250,
        "pvp_trousers_eur": 175,
        "wool_percentage": "100%",
        "made_to_measure": True,
        "brand_type": "own_brand",
        "brand_style": "Traditional/Bespoke",
        "business_model": "Retail/Bespoke",
        "tier": "medium_value",
        "notes": "Marca jajoan, PVP a partir de 375€",
        "description": "Spanish tailoring company operating under the Jajoan brand. Traditional and bespoke style with a focus on classic Spanish sastrería — structured, elegant suits in 100% wool. Entry-level premium pricing: suits from €375, jackets €250, trousers €175. Retail and bespoke business model with 6 stores across Spain. Made-to-measure service is a core offering. Target customer is the Spanish man seeking traditional tailoring at accessible prices. 7-year partnership with Lança.",
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
        "pvp_jacket_eur": 500,
        "pvp_trousers_eur": 350,
        "wool_percentage": "100%",
        "made_to_measure": True,
        "brand_type": "own_brand",
        "brand_style": "Heritage/Scottish",
        "business_model": "Retail/Bespoke",
        "tier": "medium_value",
        "notes": "Especialista em tweed escocês",
        "description": "Scottish heritage menswear brand specialising in tweed suits, jackets and country-inspired formal wear. Known for bold patterns, Harris Tweed and traditional Scottish tailoring with a contemporary edge. Suits from £650 (€800), jackets £400 (€500), trousers £280 (€350). Retail and bespoke business model with 5 stores, primarily in Edinburgh. Made-to-measure service using 100% wool fabrics. Target customer is the man seeking distinctive British country-style tailoring. 5-year partnership with Lança.",
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
        "pvp_jacket_eur": 500,
        "pvp_trousers_eur": 350,
        "wool_percentage": "100%",
        "made_to_measure": True,
        "brand_type": "multibrand",
        "brand_style": "Premium",
        "business_model": "Retail",
        "tier": "medium_value",
        "notes": "Loja multimarca em Derby",
        "description": "British multi-brand menswear retailer based in Derby. Curates premium suits, jackets and formal wear from multiple European brands including Lança-manufactured ranges. Classic-premium style positioning with suits from £650 (€800), jackets £400 (€500), trousers £280 (€350). Retail model with 2 stores and a strong local reputation. Made-to-measure consultations available. Target customer is the East Midlands professional seeking quality tailoring. One of the longest-standing Lança partnerships at 10 years.",
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
        "pvp_jacket_eur": 650,
        "pvp_trousers_eur": 450,
        "wool_percentage": "100%",
        "made_to_measure": True,
        "brand_type": "own_brand",
        "brand_style": "Bespoke/Contemporary",
        "business_model": "Bespoke",
        "tier": "medium_value",
        "notes": "Alfaiate bespoke em Brighton",
        "description": "British bespoke and contemporary tailor based in Brighton. Known for bold, creative tailoring that blends classic menswear with contemporary design — loud linings, unconventional fabrics, distinctive cuts. Suits from £800 (€1000), jackets £520 (€650), trousers £360 (€450). Exclusively bespoke and made-to-measure business model from a single Brighton atelier. 100% wool and luxury natural fabrics. Target customer is the creative professional and fashion-forward man. Celebrity clientele. 10-year bespoke partnership with Lança.",
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
        "pvp_jacket_eur": 380,
        "pvp_trousers_eur": 280,
        "wool_percentage": "100%",
        "made_to_measure": True,
        "brand_type": "own_brand",
        "brand_style": "Premium/Spanish",
        "business_model": "Retail",
        "tier": "low_value",
        "notes": "Cliente recente, marca própria em Madrid",
        "description": "Spanish premium menswear brand based in Madrid. Modern take on Spanish tailoring — clean, slim silhouettes with Mediterranean influence. 100% wool suits and jackets. Suits from €600, jackets €380, trousers €280. Own-brand retail model with a single Madrid boutique and made-to-measure offering. Target customer is the young Madrid professional seeking modern tailoring. Recent Lança client (2-3 years), growing partnership.",
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
        "pvp_jacket_eur": 500,
        "pvp_trousers_eur": 350,
        "wool_percentage": "100%",
        "made_to_measure": True,
        "brand_type": "own_brand",
        "brand_style": "Contemporary/Premium",
        "business_model": "Retail",
        "tier": "low_value",
        "notes": "Marca Flax London",
        "description": "London-based contemporary menswear brand operating under the Flax London label. Modern, relaxed tailoring with a focus on natural fabrics and minimalist design. Suits from £650 (€800), jackets £400 (€500), trousers £280 (€350). Own-brand retail model with 2 London stores and made-to-measure service. 100% wool and linen blends. Target customer is the modern London professional seeking understated, high-quality tailoring. 3-year partnership with Lança.",
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
        "pvp_jacket_eur": 650,
        "pvp_trousers_eur": 450,
        "wool_percentage": "100%",
        "made_to_measure": True,
        "brand_type": "own_brand",
        "brand_style": "Heritage/Premium",
        "business_model": "Retail",
        "tier": "low_value",
        "notes": "Cliente recente com 5 lojas em Cambridge",
        "description": "British heritage menswear brand based in Cambridge. Classic English tailoring style — structured shoulders, traditional cuts, quality wool cloths. Premium to luxury pricing: suits from £800 (€1000), jackets £520 (€650), trousers £360 (€450). Own-brand retail model with 5 stores and made-to-measure service. 100% wool and tweed fabrics. Target customer is the traditional British gentleman and academic. Newer Lança partnership (2 years), rapidly growing.",
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
        "pvp_jacket_eur": 650,
        "pvp_trousers_eur": 450,
        "wool_percentage": "100%",
        "made_to_measure": True,
        "brand_type": "own_brand",
        "brand_style": "Premium/Spanish",
        "business_model": "Retail",
        "tier": "low_value",
        "notes": "Parceria de 10 anos, boutique única em Madrid",
        "description": "Spanish premium menswear brand headquartered in Madrid. Traditional Spanish sastrería refined with a modern sensibility — elegant, slim fits in rich wool fabrics. Suits from €1000, jackets €650, trousers €450. Own-brand retail model from a single Madrid boutique with made-to-measure consultations. 100% wool with meticulous construction. Target customer is the Madrid executive seeking timeless Spanish elegance. One of the longest partnerships at 10 years with Lança.",
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
        "pvp_jacket_eur": 650,
        "pvp_trousers_eur": 450,
        "wool_percentage": "100%",
        "made_to_measure": False,
        "brand_type": "own_brand",
        "brand_style": "Premium/African",
        "business_model": "Retail",
        "tier": "medium_value",
        "notes": "2 lojas em Luanda, mercado angolano",
        "description": "Angolan premium menswear brand operating under the Dealer label in Luanda. European-influenced tailoring adapted for the African luxury market — bold, refined suits in 100% wool. Suits from approximately €1000, jackets €650, trousers €450. Own-brand retail model with 2 stores in Luanda. Ready-to-wear only (no MTM). Target customer is the Angolan executive and luxury buyer. 7-year manufacturing partnership with Lança, representing Lança's African market footprint.",
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
        "pvp_jacket_eur": 500,
        "pvp_trousers_eur": 350,
        "wool_percentage": "100%",
        "made_to_measure": True,
        "brand_type": "own_brand",
        "brand_style": "Bespoke/Premium",
        "business_model": "Bespoke",
        "tier": "medium_value",
        "notes": "Só faz por medida, boutique em Ghent",
        "description": "Belgian bespoke-only tailor based in Ghent. Exclusively made-to-measure, creating individually crafted suits, jackets and trousers in premium 100% wool fabrics. Clean, understated European style with a focus on perfect fit and fabric quality. Suits from €800, jackets €500, trousers €350. Single boutique atelier model — no ready-to-wear. Target customer is the Flemish professional and connoisseur seeking bespoke tailoring. 10-year exclusive manufacturing partnership with Lança.",
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
        "pvp_jacket_eur": 650,
        "pvp_trousers_eur": 450,
        "wool_percentage": "100%",
        "made_to_measure": True,
        "brand_type": "own_brand",
        "brand_style": "Luxury/Heritage",
        "business_model": "Retail",
        "tier": "medium_value",
        "notes": "Marca Oliver Brown, 5 lojas em Londres",
        "description": "British luxury heritage menswear brand operating as Oliver Brown in London. Classic British tailoring with a focus on City and formal wear — morning suits, three-piece suits, traditional Jermyn Street quality. Suits from £800 (€1000), jackets £520 (€650), trousers £360 (€450). Own-brand retail model with 5 London stores and made-to-measure service. 100% wool and luxury cloths. Target customer is the London City professional, wedding buyer, and traditional menswear aficionado. 10-year partnership with Lança.",
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
        "pvp_jacket_eur": 480,
        "pvp_trousers_eur": 330,
        "wool_percentage": "100%",
        "made_to_measure": False,
        "brand_type": "own_brand",
        "brand_style": "Premium/Contemporary",
        "business_model": "Retail",
        "tier": "medium_value",
        "notes": "Marca Anthony's London, 8 lojas na República Checa",
        "description": "Czech menswear retailer operating the Anthony's London brand with 8 stores across the Czech Republic. British-inspired contemporary tailoring — modern fits with classic English details, aimed at the Central European market. Suits from approximately €750, jackets €480, trousers €330. Own-brand retail model with ready-to-wear focus (no MTM). 100% wool garments manufactured by Lança. Target customer is the Czech professional seeking accessible British-style tailoring. 6-year manufacturing partnership.",
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
    "price_ranges": {
        "complete_suit": {"min": 500, "max": 1700, "label": "Fato completo (casaco + calça)"},
        "jacket_only": {"min": 300, "max": 1000, "label": "Só casaco"},
        "trousers_only": {"min": 250, "max": 750, "label": "Só calça"},
    },
    "characteristics": [
        "Small to medium boutique (1-20 stores)",
        "Premium pricing: Suits €500-€1,700 | Jackets €300-€1,000 | Trousers €250-€750",
        "Long-term partnership oriented (5+ years)",
        "Own brand focus (not multi-brand)",
        "Made-to-measure capability preferred",
        "100% wool suits",
        "European or Americas market",
        "Brand must be headquartered in target city",
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

"""
Multilingual Query Templates for Confeções Lança Prospector

Config-driven templates for Exa search queries. Three angles per language,
all focused on tailoring/MTM/classic premium menswear (narrow scope).

Each template uses {city} as a placeholder.
"""
from typing import Dict, List


# Three query angles, staying narrow: tailoring + MTM + classic premium menswear.
QUERY_ANGLES = [
    "tailoring_mtm",           # Made-to-measure / bespoke tailoring
    "independent_premium",     # Independent premium menswear boutique
    "heritage_classic",        # Heritage / classic menswear brand
]


TEMPLATES: Dict[str, Dict[str, str]] = {
    # === English (always used) ===
    "en": {
        "tailoring_mtm":
            "independent tailored suits made to measure menswear boutique {city}",
        "independent_premium":
            "premium independent menswear brand suits {city}",
        "heritage_classic":
            "heritage classic menswear tailoring brand {city}",
    },

    # === Italian ===
    "it": {
        "tailoring_mtm":
            "sartoria su misura uomo boutique {city}",
        "independent_premium":
            "abiti uomo boutique indipendente premium {city}",
        "heritage_classic":
            "sarto classico abiti uomo marca indipendente {city}",
    },

    # === French ===
    "fr": {
        "tailoring_mtm":
            "tailleur sur mesure homme indépendant {city}",
        "independent_premium":
            "boutique costume homme premium indépendante {city}",
        "heritage_classic":
            "maison costume classique homme {city}",
    },

    # === German ===
    "de": {
        "tailoring_mtm":
            "maßschneider herren boutique {city}",
        "independent_premium":
            "herrenanzug premium unabhängig boutique {city}",
        "heritage_classic":
            "klassische herrenmode maßkonfektion {city}",
    },

    # === Spanish ===
    "es": {
        "tailoring_mtm":
            "sastrería a medida hombre independiente {city}",
        "independent_premium":
            "trajes hombre boutique premium independiente {city}",
        "heritage_classic":
            "sastrería clásica hombre marca independiente {city}",
    },

    # === Portuguese ===
    "pt": {
        "tailoring_mtm":
            "alfaiataria sob medida homem boutique {city}",
        "independent_premium":
            "fato homem boutique premium independente {city}",
        "heritage_classic":
            "alfaiate clássico homem marca independente {city}",
    },

    # === Dutch ===
    "nl": {
        "tailoring_mtm":
            "maatpak heren boutique {city}",
        "independent_premium":
            "herenmode premium onafhankelijke boutique {city}",
        "heritage_classic":
            "klassieke kleermaker herenpakken {city}",
    },

    # === Catalan ===
    "ca": {
        "tailoring_mtm":
            "sastreria a mida home boutique {city}",
        "independent_premium":
            "vestits home boutique premium independent {city}",
        "heritage_classic":
            "sastreria clàssica home marca independent {city}",
    },

    # === Swedish ===
    "sv": {
        "tailoring_mtm":
            "skrädderi måttsydd kostym herrboutique {city}",
        "independent_premium":
            "herrmode oberoende boutique kostym premium {city}",
        "heritage_classic":
            "klassisk herrskrädderi varumärke {city}",
    },

    # === Norwegian Bokmål (nb is ISO standard; no kept as alias) ===
    "nb": {
        "tailoring_mtm":
            "skreddersydd dress herre boutique {city}",
        "independent_premium":
            "herremote uavhengig premium boutique dress {city}",
        "heritage_classic":
            "klassisk herreskredderi merke {city}",
    },
    "no": {
        "tailoring_mtm":
            "skreddersydd dress herre boutique {city}",
        "independent_premium":
            "herremote uavhengig premium boutique dress {city}",
        "heritage_classic":
            "klassisk herreskredderi merke {city}",
    },

    # === Danish ===
    "da": {
        "tailoring_mtm":
            "skræddersyet jakkesæt herre boutique {city}",
        "independent_premium":
            "herretøj uafhængig premium butik jakkesæt {city}",
        "heritage_classic":
            "klassisk herreskrædderi mærke {city}",
    },

    # === Finnish ===
    "fi": {
        "tailoring_mtm":
            "mittojen mukaan puku miesten boutique {city}",
        "independent_premium":
            "miesten puku premium itsenäinen myymälä {city}",
        "heritage_classic":
            "klassinen miesten räätälöinti brändi {city}",
    },

    # === Japanese ===
    "ja": {
        "tailoring_mtm":
            "オーダースーツ メンズ 仕立て {city}",
        "independent_premium":
            "メンズスーツ プレミアム 独立ブランド {city}",
        "heritage_classic":
            "クラシック テーラー メンズ {city}",
    },
}


def get_templates_for_language(lang: str) -> Dict[str, str]:
    """Get templates for a language code. Falls back to English."""
    return TEMPLATES.get(lang, TEMPLATES["en"])


def build_queries_for_city(city: str, languages: List[str]) -> List[Dict[str, str]]:
    """
    Build the full query set for a city given its language(s).

    Always includes 3 English queries. Adds 3 per local language (deduped
    if local language is English).

    Returns list of dicts: [{query, language, origin}, ...]
    """
    queries = []

    # Always: 3 English queries
    en_templates = TEMPLATES["en"]
    for angle in QUERY_ANGLES:
        queries.append({
            "query": en_templates[angle].format(city=city),
            "language": "en",
            "origin": f"EN_{angle}",
        })

    # Local language queries (skip if language is English)
    for lang in languages:
        if lang == "en":
            continue
        lang_templates = TEMPLATES.get(lang)
        if not lang_templates:
            continue
        for angle in QUERY_ANGLES:
            template = lang_templates.get(angle)
            if template:
                queries.append({
                    "query": template.format(city=city),
                    "language": lang,
                    "origin": f"{lang.upper()}_{angle}",
                })

    return queries

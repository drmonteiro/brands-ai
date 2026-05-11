"""
Static city → primary commerce language(s) (ISO 639-1).

Used to skip slow LLM language inference for common cities.
Unknown cities fall back to LLM in query_builder.infer_city_languages.
"""
from typing import Dict, List, Optional

# Normalized keys: lowercased, stripped ASCII-friendly aliases where useful.
CITY_LANGUAGE_MAP: Dict[str, List[str]] = {
    # Nordic
    "stockholm": ["sv"],
    "göteborg": ["sv"],
    "gothenburg": ["sv"],
    "malmö": ["sv"],
    "malmo": ["sv"],
    "oslo": ["nb"],
    "bergen": ["nb"],
    "copenhagen": ["da"],
    "københavn": ["da"],
    "kobenhavn": ["da"],
    "aarhus": ["da"],
    "århus": ["da"],
    "helsinki": ["fi"],
    "tampere": ["fi"],
    "reykjavik": ["en"],
    "réykjavík": ["en"],
    # Western EU
    "paris": ["fr"],
    "lyon": ["fr"],
    "marseille": ["fr"],
    "brussels": ["fr", "nl"],
    "bruxelles": ["fr", "nl"],
    "amsterdam": ["nl"],
    "rotterdam": ["nl"],
    "luxembourg": ["fr", "de"],
    "vienna": ["de"],
    "wien": ["de"],
    "berlin": ["de"],
    "munich": ["de"],
    "münchen": ["de"],
    "munchen": ["de"],
    "hamburg": ["de"],
    "frankfurt": ["de"],
    "cologne": ["de"],
    "köln": ["de"],
    "koln": ["de"],
    "zurich": ["de"],
    "zürich": ["de"],
    "geneva": ["fr"],
    "genève": ["fr"],
    # Southern EU
    "madrid": ["es"],
    "barcelona": ["es", "ca"],
    "valencia": ["es"],
    "seville": ["es"],
    "milano": ["it"],
    "milan": ["it"],
    "roma": ["it"],
    "rome": ["it"],
    "napoli": ["it"],
    "naples": ["it"],
    "lisbon": ["pt"],
    "lisboa": ["pt"],
    "porto": ["pt"],
    "athens": ["el"],
    "athina": ["el"],
    # Central / Eastern EU
    "warsaw": ["pl"],
    "krakow": ["pl"],
    "prague": ["cs"],
    "praha": ["cs"],
    "budapest": ["hu"],
    "bucharest": ["ro"],
    "sofia": ["bg"],
    "zagreb": ["hr"],
    "ljubljana": ["sl"],
    "bratislava": ["sk"],
}

# Americas (non–English-primary metros still useful for map fast-path)
CITY_LANGUAGE_MAP.update({
    "mexico city": ["es"],
    "ciudad de méxico": ["es"],
    "são paulo": ["pt"],
    "sao paulo": ["pt"],
    "rio de janeiro": ["pt"],
    "buenos aires": ["es"],
    "santiago": ["es"],
    "bogotá": ["es"],
    "bogota": ["es"],
    "lima": ["es"],
    "montreal": ["fr", "en"],
})

# Asia / Middle East
CITY_LANGUAGE_MAP.update({
    "tokyo": ["ja"],
    "osaka": ["ja"],
    "kyoto": ["ja"],
    "seoul": ["ko"],
    "shanghai": ["zh"],
    "beijing": ["zh"],
    "hong kong": ["en", "zh"],
    "singapore": ["en"],
    "dubai": ["en", "ar"],
    "tel aviv": ["he", "en"],
    "istanbul": ["tr"],
})


def lookup_city_languages(city: str) -> Optional[List[str]]:
    """Return language list if city is in the map, else None."""
    if not city:
        return None
    key = city.lower().strip()
    langs = CITY_LANGUAGE_MAP.get(key)
    if langs is not None:
        return list(langs)
    return None

from typing import List, Optional, Tuple
from pydantic import BaseModel, Field
from selectolax.parser import HTMLParser
import logging
import re

logger = logging.getLogger(__name__)

# Constants for extraction reasons
REASON_NO_PRICES = "no_prices"
REASON_NO_STORES = "no_stores"
REASON_NO_BRAND = "no_brand"
REASON_PRICES_OUT_OF_RANGE = "prices_out_of_range"
REASON_PRICES_TYPE_MISMATCH = "prices_type_mismatch"

class PriceItem(BaseModel):
    value: float = Field(description="The numeric value of the price.")
    currency: str = Field(description="The currency symbol or code (e.g., EUR, €, $, GBP).")

class StoreAddress(BaseModel):
    address: str = Field(description="The full street address of the physical store.")
    city: str = Field(description="The city where the store is located.")
    country: str = Field(description="The country where the store is located. Mandatory.")

class ExtractedBoutiqueData(BaseModel):
    prices: List[PriceItem] = Field(default_factory=list, description="List of prices found for complete suits or formal jackets.")
    store_addresses: List[StoreAddress] = Field(default_factory=list, description="List of physical store locations owned by the brand.")
    brand_name: Optional[str] = Field(None, description="The official name of the brand or boutique.")
    price_source: Optional[str] = Field(
        default=None, 
        description="'css' se extraído via Camada 1, 'llm' se via Camada 2, 'mixed' ou 'none'"
    )

class CSSExtractor:
    def __init__(self, schema: dict = None):
        self.schema = schema or {}

    def _parse_price_text(self, raw: str) -> Optional[float]:
        """
        '€1,250.00' → 1250.0
        '1.250,00 €' → 1250.0  (formato europeu)
        'from $890' → 890.0
        'Contact for price' → None
        """
        # Remove tudo que não seja dígito, vírgula, ou ponto
        cleaned = re.sub(r"[^\d.,]", "", raw)
        if not cleaned:
            return None
        try:
            # Heurística: se tem vírgula depois de ponto, é formato EU
            # 1.250,00 → 1250.00
            if "," in cleaned and "." in cleaned:
                if cleaned.rindex(",") > cleaned.rindex("."):
                    cleaned = cleaned.replace(".", "").replace(",", ".")
                else:
                    cleaned = cleaned.replace(",", "")
            elif "," in cleaned:
                # Pode ser milhar (1,250) ou decimal (250,00)
                parts = cleaned.split(",")
                if len(parts[-1]) == 2:
                    cleaned = cleaned.replace(",", ".")  # decimal EU
                else:
                    cleaned = cleaned.replace(",", "")  # milhar US
            return float(cleaned)
        except ValueError:
            return None

    def extract(self, cleaned_html: str) -> ExtractedBoutiqueData:
        """Applies CSS rules via Selectolax to the HTML and returns structured data."""
        if not cleaned_html:
            return ExtractedBoutiqueData()
            
        tree = HTMLParser(cleaned_html)
        data = ExtractedBoutiqueData()

        # 1. Extract Prices
        price_selectors = [
            "[itemprop='price']", ".price", ".product-price", "[data-price]", 
            ".money", ".amount", ".price-item", ".price__regular", 
            ".product-single__price", ".current-price", ".onsale"
        ]
        price_nodes = []
        for sel in price_selectors:
            price_nodes.extend(tree.css(sel))

        for node in price_nodes:
            val_str = node.text(strip=True)
            if not val_str: continue
            currency = node.attributes.get("data-currency", "")
            if not currency:
                if '€' in val_str or 'EUR' in val_str: currency = 'EUR'
                elif '$' in val_str: currency = 'USD'
                elif '£' in val_str: currency = 'GBP'

            val_float = self._parse_price_text(val_str)
            if val_float is not None:
                data.prices.append(PriceItem(value=val_float, currency=currency))

        # 2. Extract Store Addresses
        store_selectors = [
            "[itemtype*='PostalAddress']", ".store-address", ".location-card",
            ".store-info", ".address", ".physical-store", ".boutique-address"
        ]
        store_nodes = []
        for sel in store_selectors:
            store_nodes.extend(tree.css(sel))

        for node in store_nodes:
            address = node.text(strip=True)
            city_node = node.css_first("[itemprop='addressLocality']")
            country_node = node.css_first("[itemprop='addressCountry']")
            
            city = city_node.text(strip=True) if city_node else ""
            country = country_node.text(strip=True) if country_node else ""
            
            if address or city or country:
                data.store_addresses.append(StoreAddress(
                    address=address,
                    city=city,
                    country=country
                ))

        # 3. Extract Brand Name
        brand_selectors = [
            "[itemprop='brand']", "meta[property='og:site_name']",
            ".brand-name", ".logo img", ".header-logo img", "meta[name='author']"
        ]
        for sel in brand_selectors:
            if sel.startswith("meta"):
                node = tree.css_first(sel)
                if node:
                    data.brand_name = node.attributes.get("content")
                    if data.brand_name: break
            else:
                node = tree.css_first(sel)
                if node:
                    data.brand_name = node.attributes.get("alt") or node.text(strip=True)
                    if data.brand_name: break

        return data

    def extraction_quality_score(self, result: ExtractedBoutiqueData) -> Tuple[float, List[str]]:
        """
        Returns (score 0-1, list of reasons for fallback).
        Low score = trigger Layer 2.
        """
        score = 1.0
        reasons = []

        if not result.prices:
            score -= 0.3
            reasons.append(REASON_NO_PRICES)
        else:
            valid = [p for p in result.prices if 50 <= p.value <= 10000]
            if len(valid) < len(result.prices) / 2:
                score -= 0.2
                reasons.append(REASON_PRICES_OUT_OF_RANGE)

        if not result.store_addresses:
            score -= 0.3
            reasons.append(REASON_NO_STORES)
            
        if not result.brand_name:
            score -= 0.1
            reasons.append(REASON_NO_BRAND)

        return max(0.0, score), reasons

css_extractor = CSSExtractor()

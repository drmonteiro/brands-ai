"""
Price Extraction Service
Extracts and averages suit prices from text content.
"""
import re
from typing import Dict

def extract_price_from_content(content: str) -> Dict[str, float]:
    """
    Heuristic to find average price in content for rapid filtering.
    Supports various currency formats (€, $, £).
    """
    if not content:
        return {"avg_price": 0}
        
    # Search for price patterns: $1,299 or €1.299 or 899€ or 500 EUR
    # Captured groups handle both prefix and suffix currencies
    patterns = [
        r'[$€£]\s?(\d{1,3}(?:[,.]\d{3})*(?:[.,]\d{2})?)', # Prefix
        r'(\d{1,3}(?:[,.]\d{3})*(?:[.,]\d{2})?)\s?[$€£]', # Suffix
        r'(\d{1,3}(?:[,.]\d{3})*(?:[.,]\d{2})?)\s?EUR'     # Text EUR
    ]
    
    all_prices = []
    
    for pattern in patterns:
        matches = re.findall(pattern, content)
        for m in matches:
            try:
                # Basic cleaning: remove dots/commas to get raw numbers
                # We assume if there's both , and . it's a decimal format 1.299,00
                if ',' in m and '.' in m:
                    # Heuristic: Suit prices are usually > 100, so 1.299,00 -> 1299
                    val_str = m.replace(',', '').replace('.', '')
                    val = float(val_str) / 100
                elif ',' in m:
                    # Could be 1,299 or 12,99
                    val_str = m.replace(',', '')
                    val = float(val_str)
                elif '.' in m:
                    # Could be 1.299 or 12.99
                    val_str = m.replace('.', '')
                    val = float(val_str)
                else:
                    val = float(m)
                
                # Filter reasonable suit prices (between 150 and 6000 EUR)
                if 150 < val < 6000:
                    all_prices.append(val)
            except Exception:
                continue
            
    if not all_prices:
        return {"avg_price": 0}
        
    avg_price = sum(all_prices) / len(all_prices)
    return {"avg_price": avg_price}

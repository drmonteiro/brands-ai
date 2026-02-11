"""
Data module for Confeções Lança
"""

from .lanca_clients import (
    LANCA_CLIENTS,
    MARKET_STRENGTH,
    MARKET_STRENGTH_STATIC,
    get_clients_by_tier,
    get_clients_by_country,
    get_market_strength,
    get_top_clients,
    TOTAL_CLIENTS,
)

__all__ = [
    "LANCA_CLIENTS",
    "MARKET_STRENGTH",
    "MARKET_STRENGTH_STATIC",
    "get_clients_by_tier",
    "get_clients_by_country",
    "get_market_strength",
    "get_top_clients",
    "TOTAL_CLIENTS",
]

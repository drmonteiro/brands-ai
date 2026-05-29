"""
Central EUR ↔ USD conversion for Confeções Lança.

All price conversions must go through this module (never inline * 1.08).
"""

import os
from typing import Optional

_DEFAULT_RATE = 1.08


def get_eur_usd_rate() -> float:
    """EUR→USD rate from EUR_USD_RATE env var (default 1.08)."""
    raw = os.getenv("EUR_USD_RATE", str(_DEFAULT_RATE))
    try:
        rate = float(raw)
        if rate <= 0:
            raise ValueError("rate must be positive")
        return rate
    except (TypeError, ValueError):
        return _DEFAULT_RATE


def eur_to_usd(eur: float, rate: Optional[float] = None) -> float:
    r = rate if rate is not None else get_eur_usd_rate()
    return float(eur) * r


def usd_to_eur(usd: float, rate: Optional[float] = None) -> float:
    r = rate if rate is not None else get_eur_usd_rate()
    return float(usd) / r

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


def _fx_env(name: str, default: str) -> float:
    try:
        v = float(os.getenv(name, default))
        return v if v > 0 else float(default)
    except (TypeError, ValueError):
        return float(default)


# Approximate FX → EUR for LLM extraction prompts (configurable, not live FX)
GBP_TO_EUR = _fx_env("GBP_TO_EUR", "1.17")
USD_TO_EUR = _fx_env("USD_TO_EUR", "0.93")
CHF_TO_EUR = _fx_env("CHF_TO_EUR", "1.05")


def extraction_fx_rules_text() -> str:
    """Pricing conversion lines for enrichment LLM prompts."""
    eur_usd = get_eur_usd_rate()
    return (
        f"- Convert all prices to EUR using: £1 ≈ €{GBP_TO_EUR}, "
        f"$1 ≈ €{USD_TO_EUR}, CHF 1 ≈ €{CHF_TO_EUR} "
        f"(reference EUR→USD: 1 EUR ≈ {eur_usd} USD)"
    )

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


# Approximate rates to EUR, kept simple on purpose: they place a price in a band, not
# on an invoice. Override any with <CODE>_TO_EUR.
_TO_EUR = {
    "EUR": 1.0,
    "GBP": GBP_TO_EUR,
    "USD": USD_TO_EUR,
    "CHF": CHF_TO_EUR,
    "CAD": _fx_env("CAD_TO_EUR", "0.68"),
    "AUD": _fx_env("AUD_TO_EUR", "0.61"),
    "NZD": _fx_env("NZD_TO_EUR", "0.56"),
    "SEK": _fx_env("SEK_TO_EUR", "0.088"),
    "NOK": _fx_env("NOK_TO_EUR", "0.086"),
    "DKK": _fx_env("DKK_TO_EUR", "0.134"),
    "PLN": _fx_env("PLN_TO_EUR", "0.23"),
    "CZK": _fx_env("CZK_TO_EUR", "0.04"),
    "HUF": _fx_env("HUF_TO_EUR", "0.0026"),
    "JPY": _fx_env("JPY_TO_EUR", "0.0062"),
    "SGD": _fx_env("SGD_TO_EUR", "0.69"),
    "HKD": _fx_env("HKD_TO_EUR", "0.12"),
    "AED": _fx_env("AED_TO_EUR", "0.25"),
}


def to_eur(amount: float, currency: str) -> Optional[float]:
    """Amount in EUR, or None for an unknown currency: a price we can't place isn't a price."""
    rate = _TO_EUR.get((currency or "").strip().upper())
    return float(amount) * rate if rate is not None else None


def extraction_fx_rules_text() -> str:
    """Pricing conversion lines for enrichment LLM prompts."""
    eur_usd = get_eur_usd_rate()
    return (
        f"- Convert all prices to EUR using: £1 ≈ €{GBP_TO_EUR}, "
        f"$1 ≈ €{USD_TO_EUR}, CHF 1 ≈ €{CHF_TO_EUR} "
        f"(reference EUR→USD: 1 EUR ≈ {eur_usd} USD)"
    )

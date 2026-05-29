"""Tests for central EUR/USD conversion."""

import os

import pytest

from services.currency import (
    eur_to_usd,
    extraction_fx_rules_text,
    get_eur_usd_rate,
    usd_to_eur,
)


def test_default_rate():
    os.environ.pop("EUR_USD_RATE", None)
    assert get_eur_usd_rate() == 1.08
    assert eur_to_usd(100) == 108.0
    assert usd_to_eur(108) == 100.0


def test_env_override(monkeypatch):
    monkeypatch.setenv("EUR_USD_RATE", "1.10")
    assert get_eur_usd_rate() == 1.10
    assert eur_to_usd(50) == pytest.approx(55.0)


def test_extraction_fx_rules_text_includes_rates():
    text = extraction_fx_rules_text()
    assert "€1.17" in text or "1.17" in text
    assert "EUR" in text

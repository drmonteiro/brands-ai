"""Prices count only with proof from the brand's own site, for a whole suit."""

import pytest

from services.currency import to_eur
from services.price_evidence import confirm_suit_prices, is_whole_suit, parse_amount, same_site

SITE = "https://www.brand.test"
TEXT = "Our classic two-piece suit is £1,295. Silk ties from £95. Costume homme 1.495,00 €"


def _finding(**overrides):
    return {
        "amount": 1295,
        "currency": "GBP",
        "product": "classic two-piece suit",
        "quote": "two-piece suit is £1,295",
        "source_url": "https://brand.test/suits",
        **overrides,
    }


@pytest.mark.parametrize("raw,expected", [
    ("1,295", 1295), ("1.295", 1295), ("1.295,00", 1295), ("1,295.00", 1295),
    ("495,00", 495), ("495.50", 495.5), ("1'295", 1295), ("1 295", 1295),
    ("€2.500", 2500), ("12.500,50", 12500.5), (850, 850), ("", None), (None, None),
    ("free", None), (0, None), (True, None),
])
def test_parse_amount(raw, expected):
    assert parse_amount(raw) == expected


@pytest.mark.parametrize("product,expected", [
    ("two-piece suit", True), ("Fato completo", True), ("abito su misura", True),
    ("Maßanzug", True), ("Anzug", True), ("Bespoke suits", True),
    ("suit jacket", False), ("suit trousers", False), ("swimsuit", False),
    ("tracksuit", False), ("suit bag", False), ("suit hire", False), ("silk tie", False),
    ("blazer", False), ("suit rental", False), ("suit alterations", False),
])
def test_only_whole_suits_count(product, expected):
    assert is_whole_suit(product) is expected


def test_valid_finding_is_confirmed_and_converted():
    out = confirm_suit_prices([_finding()], SITE, TEXT)
    assert out["price_status"] == "confirmed"
    assert out["avg_suit_price_eur"] == pytest.approx(to_eur(1295, "GBP"), abs=0.01)
    assert out["price_source_url"] == "https://brand.test/suits"
    assert out["price_evidence"][0]["quote"] == "two-piece suit is £1,295"


def test_no_findings_is_unconfirmed_never_a_guess():
    out = confirm_suit_prices([], SITE, TEXT)
    assert out["price_status"] == "unconfirmed"
    assert out["avg_suit_price_eur"] is None
    assert out["price_evidence"] == []


@pytest.mark.parametrize("overrides", [
    {"quote": "two-piece suit is £999", "amount": 999},  # not in the source text
    {"quote": "two-piece suit is £1,295", "amount": 1500},  # amount not in the quote
    {"source_url": "https://other-shop.test/suits"},  # another website's price
    {"product": "silk tie", "amount": 95, "quote": "Silk ties from £95"},  # not a suit
    {"currency": "XXX"},  # unknown currency
    {"currency": ""},
    {"quote": "£1,295"},  # too short to prove anything
])
def test_invalid_findings_are_ignored(overrides):
    assert confirm_suit_prices([_finding(**overrides)], SITE, TEXT)["price_status"] == "unconfirmed"


def test_european_format_in_quote_is_accepted():
    finding = _finding(amount="1.495,00", currency="EUR", product="Costume homme", quote="Costume homme 1.495,00 €")
    out = confirm_suit_prices([finding], SITE, TEXT)
    assert out["avg_suit_price_eur"] == 1495


def test_quote_matches_despite_markdown_and_spacing():
    finding = _finding(quote="two-piece suit is £1,295")
    text = "**Our classic   two-piece suit** is\n£1,295."
    assert confirm_suit_prices([finding], SITE, text)["price_status"] == "confirmed"


def test_range_only_uses_suits_ignoring_other_products():
    other = _finding(amount=95, product="silk tie", quote="Silk ties from £95")
    assert confirm_suit_prices([_finding(), other], SITE, TEXT)["price_range_min_eur"] > 1000


def test_malformed_findings_do_not_crash():
    assert confirm_suit_prices(["x", None, {}], SITE, TEXT)["price_status"] == "unconfirmed"
    assert confirm_suit_prices("nonsense", SITE, TEXT)["price_status"] == "unconfirmed"


@pytest.mark.parametrize("url,expected", [
    ("https://brand.test/a", True), ("https://shop.brand.test/a", True),
    ("https://www.brand.test", True), ("https://notbrand.test", False),
    ("https://brand.test.evil.example", False), ("", False),
])
def test_same_site(url, expected):
    assert same_site(url, SITE) is expected


def test_to_eur_handles_local_currencies_and_rejects_unknown():
    assert to_eur(100, "EUR") == 100
    assert 50 < to_eur(100, "cad") < 90
    assert 5 < to_eur(100, "SEK") < 15
    assert to_eur(100, "XXX") is None

"""
Decides whether a brand is a lead Lança should see.

A great lead sells suits or tailoring, is at the level of Lança's current clients,
and respects the price and store rules. Pure functions: the reasons are stored, so
every rejection can be explained and the rules tuned.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional

from services.lead_rules import (
    ACCEPTED_CATEGORIES,
    MIN_FIT,
    PRICE_REJECT_ABOVE,
    PRICE_REJECT_BELOW,
    STORES_REJECT_ABOVE,
    STRONG_FIT,
    STRONG_SIMILARITY,
)


@dataclass(frozen=True)
class GateDecision:
    accepted: bool
    code: Optional[str] = None
    reason: str = ""


def _reject(code: str, reason: str) -> GateDecision:
    return GateDecision(False, code, reason)


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def evaluate_lead(brand: Dict[str, Any]) -> GateDecision:
    if brand.get("_extraction_failed"):
        return _reject("extraction_failed", "Não foi possível analisar o site da marca.")

    if brand.get("is_official_site") is False:
        return _reject("not_official_site", "O endereço é um diretório ou artigo, não o site da marca.")

    category = brand.get("core_category")
    if category not in ACCEPTED_CATEGORIES:
        return _reject("not_suit_brand", f"Fatos não são um produto central (categoria: {category or 'desconhecida'}).")
    if brand.get("suit_evidence_verified") is not True:
        return _reject("no_suit_evidence", "Sem prova no site de que vende fatos ou alfaiataria.")
    if brand.get("target_gender") == "women":
        return _reject("womenswear_only", "Marca só de senhora.")
    if brand.get("is_chain") is True:
        return _reject("chain", "Cadeia ou marketplace, não uma marca independente.")

    stores = int(_number(brand.get("store_count")))
    if stores > STORES_REJECT_ABOVE:
        return _reject("too_many_stores", f"{stores} lojas, acima do limite de {STORES_REJECT_ABOVE}.")

    # Judged on the range: a tailor with made-to-measure at €1100 isn't out of reach
    # because its bespoke line costs €4000.
    confirmed = brand.get("price_status") == "confirmed"
    average = _number(brand.get("avg_suit_price_eur"))
    lowest = _number(brand.get("price_range_min_eur")) or average
    highest = _number(brand.get("price_range_max_eur")) or average
    if confirmed and highest < PRICE_REJECT_BELOW:
        return _reject("price_too_low", f"Fatos até €{highest:.0f}, abaixo do mínimo de €{PRICE_REJECT_BELOW:.0f}.")
    if confirmed and lowest > PRICE_REJECT_ABOVE:
        return _reject("price_too_high", f"Fatos desde €{lowest:.0f}, acima do máximo de €{PRICE_REJECT_ABOVE:.0f}.")

    if brand.get("similarity_failed"):
        return _reject("similarity_failed", "Não foi possível comparar com os clientes atuais.")

    level = brand.get("client_level")
    fit = _number(brand.get("llm_fit_score"))
    if level is None:
        return _reject("level_unknown", "Não foi possível avaliar o nível da marca.")
    # "above" passes only with a confirmed price: the price rule already caps how high
    # a brand can be, and without a price there's nothing to show it's within reach.
    level_ok = level == "same" or (level == "above" and confirmed)
    if not level_ok or fit < MIN_FIT:
        return _reject("wrong_level", f"Nível diferente dos clientes atuais ({level}, encaixe {fit:.0f}/10).")

    if not confirmed:
        similarity = _number(brand.get("similarity_score"))
        tailoring = category == "tailoring_core" or brand.get("made_to_measure") is True
        if fit < STRONG_FIT or similarity < STRONG_SIMILARITY or not tailoring:
            return _reject(
                "unconfirmed_price_weak_fit",
                f"Sem preço confirmado e sem encaixe forte (encaixe {fit:.0f}/10, semelhança {similarity:.0f}).",
            )

    return GateDecision(True)

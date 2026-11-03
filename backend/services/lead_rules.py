"""The lead rules, read from rubric.yaml so ranking, the gate and evaluation can't disagree."""

from pathlib import Path

import yaml

_rubric = yaml.safe_load((Path(__file__).resolve().parent.parent / "rubric.yaml").read_text())
_critical = {c["id"]: c for c in _rubric["critical_criteria"]}
_price = _critical["price_range"]
_stores = _critical["store_count"]
_gate = _rubric["lead_gate"]

PRICE_IDEAL_MIN = float(_price["min"])
PRICE_IDEAL_MAX = float(_price["max"])
PRICE_REJECT_BELOW = float(_price["hard_reject_below"])
PRICE_REJECT_ABOVE = float(_price["hard_reject_above"])

STORES_IDEAL_MAX = int(_stores["max"])
STORES_REJECT_ABOVE = int(_stores["hard_reject_above"])

MIN_FIT = float(_gate["min_fit"])
STRONG_FIT = float(_gate["strong_fit"])
STRONG_SIMILARITY = float(_gate["strong_similarity"])
ACCEPTED_CATEGORIES = frozenset(_gate["accepted_categories"])

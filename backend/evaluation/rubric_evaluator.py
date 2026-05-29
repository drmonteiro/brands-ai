"""
Rubric Evaluator for Confeções Lança Prospector

Loads rubric.yaml and evaluates pipeline output (list of brand dicts for a city).
Produces JSON + markdown report with per-criterion pass/fail rates,
score distributions, and store/price distributions.
"""
import json
import os
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from services.currency import usd_to_eur


RUBRIC_PATH = Path(__file__).resolve().parent.parent / "rubric.yaml"


def load_rubric(path: Optional[str] = None) -> Dict:
    p = Path(path) if path else RUBRIC_PATH
    with open(p) as f:
        return yaml.safe_load(f)


# ============================================================================
# Field extraction helpers — normalise raw pipeline output into rubric fields
# ============================================================================

_TAILORING_KEYWORDS = {
    "tailoring", "tailor", "sartorial", "sartoria", "bespoke",
    "made-to-measure", "made to measure", "mtm", "sur mesure",
    "su misura", "maßschneider", "sastrería", "alfaiataria",
    "classic premium", "premium menswear", "heritage menswear",
}


def _infer_style_category(brand: Dict) -> Optional[str]:
    """Map brand_style / business_model to one of the rubric enum values."""
    style = (brand.get("brand_style") or "").lower()
    model = (brand.get("business_model") or "").lower()
    desc = (brand.get("detailed_description") or brand.get("company_overview") or "").lower()
    combined = f"{style} {model} {desc}"

    if any(kw in combined for kw in ("bespoke", "made-to-measure", "made to measure",
                                      "mtm", "sur mesure", "su misura", "maßschneider",
                                      "sastrería", "alfaiataria", "demi-mesure")):
        return "made_to_measure"
    if any(kw in combined for kw in ("tailor", "sartori", "tailleur")):
        return "tailoring"
    if any(kw in combined for kw in ("premium", "heritage", "classic", "luxury")):
        return "classic_premium_menswear"
    return None


def _parse_wool_pct(raw) -> Optional[float]:
    """Extract numeric wool percentage from string like '100%' or 'Pure wool'."""
    if raw is None:
        return None
    s = str(raw).lower()
    m = re.search(r"(\d{1,3})\s*%", s)
    if m:
        return float(m.group(1))
    if "100" in s:
        return 100.0
    if "pure" in s or "pura" in s:
        return 100.0
    if "wool" in s or "lã" in s or "lana" in s or "laine" in s:
        return 50.0  # conservative estimate
    return None


def _normalise_brand(brand: Dict) -> Dict:
    """Map raw pipeline BrandLead dict into rubric-friendly fields."""
    price = brand.get("avg_suit_price_eur") or 0
    if price == 0:
        usd = brand.get("average_suit_price_usd") or brand.get("averageSuitPriceUSD") or 0
        if usd:
            price = usd_to_eur(float(usd))
    try:
        price = float(price)
    except (TypeError, ValueError):
        price = 0

    store_count = brand.get("store_count") or brand.get("storeCount") or 0
    try:
        store_count = int(store_count)
    except (TypeError, ValueError):
        store_count = 0

    is_chain = brand.get("is_chain") or brand.get("isChain") or False
    mtm = brand.get("made_to_measure") or brand.get("madeToMeasure") or False

    return {
        "name": brand.get("name", "Unknown"),
        "avg_suit_price_eur": price,
        "store_count": store_count,
        "city_presence_type": brand.get("city_presence_type", "unknown"),
        "is_chain": bool(is_chain),
        "style_category": _infer_style_category(brand),
        "max_client_similarity": brand.get("max_client_similarity", None),
        "verified_email": bool(brand.get("contact_email") or brand.get("contactEmail")),
        "verified_phone": bool(brand.get("contact_phone") or brand.get("contactPhone")),
        "wool_percentage": _parse_wool_pct(brand.get("wool_percentage") or brand.get("woolPercentage")),
        "offers_mtm": bool(mtm),
        "appointment_only": bool(brand.get("appointment_only") or brand.get("appointmentOnly")),
        "final_score": brand.get("final_score", None),
    }


# ============================================================================
# Criterion evaluators
# ============================================================================

def _eval_range(norm: Dict, crit: Dict) -> Tuple[str, Optional[str]]:
    """Evaluate a range criterion. Returns (status, reason)."""
    val = norm.get(crit["field"])
    if val is None or val == 0:
        return "unknown", f"{crit['field']} is missing/zero"

    if "hard_reject_below" in crit and val < crit["hard_reject_below"]:
        return "hard_reject", f"{val} < hard_reject {crit['hard_reject_below']}"
    if "hard_reject_above" in crit and val > crit["hard_reject_above"]:
        return "hard_reject", f"{val} > hard_reject {crit['hard_reject_above']}"

    if crit["min"] <= val <= crit["max"]:
        return "pass", None
    return "fail", f"{val} outside [{crit['min']}, {crit['max']}]"


def _eval_boolean(norm: Dict, crit: Dict) -> Tuple[str, Optional[str]]:
    val = norm.get(crit["field"])
    if val is None:
        return "unknown", f"{crit['field']} is missing"
    if bool(val) == crit["expected"]:
        return "pass", None
    return "fail", f"{crit['field']}={val}, expected {crit['expected']}"


def _eval_enum(norm: Dict, crit: Dict) -> Tuple[str, Optional[str]]:
    val = norm.get(crit["field"])
    if val is None:
        return "unknown", f"{crit['field']} is missing"
    if val in crit["allowed"]:
        return "pass", None
    return "fail", f"{val} not in {crit['allowed']}"


def _eval_hierarchical_presence(norm: Dict, crit: Dict) -> Tuple[str, Optional[str]]:
    val = norm.get(crit["field"])
    hierarchy = crit["hierarchy"]
    min_req = crit["min_required"]
    if val is None or val == "unknown":
        return "unknown", "city_presence_type unknown"
    if val in hierarchy:
        if hierarchy.index(val) <= hierarchy.index(min_req):
            return "pass", None
        return "fail", f"{val} below minimum {min_req}"
    return "fail", f"unrecognised presence type: {val}"


def _eval_threshold(norm: Dict, crit: Dict) -> Tuple[str, Optional[str]]:
    val = norm.get(crit["field"])
    if val is None:
        return "unknown", f"{crit['field']} is missing"
    if val >= crit["min"]:
        return "pass", None
    return "fail", f"{val} < {crit['min']}"


def _eval_any_of(norm: Dict, crit: Dict) -> Tuple[str, Optional[str]]:
    if any(norm.get(f) for f in crit["fields"]):
        return "pass", None
    return "fail", f"none of {crit['fields']} present"


def _eval_progressive(norm: Dict, crit: Dict) -> Tuple[str, float]:
    val = norm.get(crit["field"])
    if val is None:
        return "unknown", 0.0
    score = max(0.0, min(1.0, (val - crit["min_value"]) / (crit["max_value"] - crit["min_value"])))
    return "pass", score


_EVALUATORS = {
    "range": _eval_range,
    "boolean": _eval_boolean,
    "enum": _eval_enum,
    "hierarchical_presence": _eval_hierarchical_presence,
    "threshold": _eval_threshold,
    "any_of": _eval_any_of,
    "progressive": _eval_progressive,
}


def evaluate_brand(norm: Dict, rubric: Dict) -> Dict:
    """Evaluate a single normalised brand against the full rubric."""
    results = {"name": norm["name"], "critical": {}, "important": {}, "bonus": {}}
    for crit in rubric.get("critical_criteria", []):
        fn = _EVALUATORS.get(crit["type"])
        if fn:
            status, detail = fn(norm, crit)
            results["critical"][crit["id"]] = {"status": status, "detail": detail}
    for crit in rubric.get("important_criteria", []):
        fn = _EVALUATORS.get(crit["type"])
        if fn:
            status, detail = fn(norm, crit)
            results["important"][crit["id"]] = {"status": status, "detail": detail}
    for crit in rubric.get("bonus_criteria", []):
        fn = _EVALUATORS.get(crit["type"])
        if fn:
            status, detail = fn(norm, crit)
            results["bonus"][crit["id"]] = {"status": status, "detail": detail}
    return results


# ============================================================================
# Report generation
# ============================================================================

def evaluate_city(brands: List[Dict], city: str, rubric: Optional[Dict] = None) -> Dict:
    """Evaluate all brands for a city. Returns structured report dict."""
    if rubric is None:
        rubric = load_rubric()

    normalised = [_normalise_brand(b) for b in brands]
    evaluations = [evaluate_brand(n, rubric) for n in normalised]

    total = len(brands)
    if total == 0:
        return {"city": city, "total_brands": 0, "error": "no brands to evaluate"}

    # Critical criteria pass rates
    crit_ids = [c["id"] for c in rubric.get("critical_criteria", [])]
    crit_fail_counts = Counter()
    brands_passing_all_critical = 0
    per_brand_crit_fails = []

    for ev in evaluations:
        fails = sum(1 for cid in crit_ids if ev["critical"].get(cid, {}).get("status") not in ("pass", "unknown"))
        per_brand_crit_fails.append(fails)
        if fails == 0:
            brands_passing_all_critical += 1
        for cid in crit_ids:
            if ev["critical"].get(cid, {}).get("status") not in ("pass", "unknown"):
                crit_fail_counts[cid] += 1

    # Important criteria
    imp_ids = [c["id"] for c in rubric.get("important_criteria", [])]
    imp_pass_counts = Counter()
    for ev in evaluations:
        for iid in imp_ids:
            if ev["important"].get(iid, {}).get("status") == "pass":
                imp_pass_counts[iid] += 1

    # Bonus criteria
    bonus_ids = [c["id"] for c in rubric.get("bonus_criteria", [])]
    bonus_met_counts = Counter()
    for ev in evaluations:
        for bid in bonus_ids:
            if ev["bonus"].get(bid, {}).get("status") == "pass":
                bonus_met_counts[bid] += 1
    avg_bonus = sum(bonus_met_counts.values()) / total if total else 0

    # Distributions
    prices = [n["avg_suit_price_eur"] for n in normalised if n["avg_suit_price_eur"] > 0]
    stores = [n["store_count"] for n in normalised if n["store_count"] > 0]
    scores = [n["final_score"] for n in normalised if n["final_score"] is not None]

    def histogram(vals, bucket_size=10):
        if not vals:
            return {}
        buckets = Counter()
        for v in vals:
            b = int(v // bucket_size) * bucket_size
            buckets[f"{b}-{b+bucket_size-1}"] = buckets.get(f"{b}-{b+bucket_size-1}", 0) + 1
        return dict(sorted(buckets.items()))

    presence_dist = Counter(n.get("city_presence_type", "unknown") for n in normalised)

    report = {
        "city": city,
        "timestamp": datetime.utcnow().isoformat(),
        "total_brands": total,
        "passing_all_critical": brands_passing_all_critical,
        "pct_passing_all_critical": round(brands_passing_all_critical / total * 100, 1),
        "pct_failing_1_critical": round(sum(1 for f in per_brand_crit_fails if f == 1) / total * 100, 1),
        "pct_failing_2_critical": round(sum(1 for f in per_brand_crit_fails if f == 2) / total * 100, 1),
        "pct_failing_3plus_critical": round(sum(1 for f in per_brand_crit_fails if f >= 3) / total * 100, 1),
        "per_criterion_failure_rate": {
            cid: round(crit_fail_counts.get(cid, 0) / total * 100, 1) for cid in crit_ids
        },
        "important_pass_rate": {
            iid: round(imp_pass_counts.get(iid, 0) / total * 100, 1) for iid in imp_ids
        },
        "avg_bonus_criteria_met": round(avg_bonus, 2),
        "bonus_met_rate": {
            bid: round(bonus_met_counts.get(bid, 0) / total * 100, 1) for bid in bonus_ids
        },
        "city_presence_distribution": dict(presence_dist),
        "score_histogram": histogram(scores),
        "store_count_distribution": histogram(stores, bucket_size=5),
        "price_distribution": histogram(prices, bucket_size=250),
        "evaluations": evaluations,
    }
    return report


def report_to_markdown(report: Dict) -> str:
    """Convert a report dict to a human-readable markdown string."""
    lines = [
        f"# Rubric Evaluation Report — {report['city']}",
        f"*Generated: {report.get('timestamp', 'N/A')}*\n",
        f"## Summary",
        f"- **Total brands:** {report['total_brands']}",
        f"- **Passing all critical criteria:** {report['passing_all_critical']} ({report['pct_passing_all_critical']}%)",
        f"- **Failing 1 critical:** {report['pct_failing_1_critical']}%",
        f"- **Failing 2 critical:** {report['pct_failing_2_critical']}%",
        f"- **Failing 3+ critical:** {report['pct_failing_3plus_critical']}%",
        f"- **Avg bonus criteria met:** {report['avg_bonus_criteria_met']}\n",
        "## Per-Criterion Failure Rate (Critical)",
    ]
    for cid, rate in report.get("per_criterion_failure_rate", {}).items():
        lines.append(f"- `{cid}`: {rate}% fail")

    lines.append("\n## Important Criteria Pass Rate")
    for iid, rate in report.get("important_pass_rate", {}).items():
        lines.append(f"- `{iid}`: {rate}% pass")

    lines.append("\n## Bonus Criteria Met Rate")
    for bid, rate in report.get("bonus_met_rate", {}).items():
        lines.append(f"- `{bid}`: {rate}% met")

    lines.append("\n## City Presence Distribution")
    for ptype, cnt in report.get("city_presence_distribution", {}).items():
        lines.append(f"- `{ptype}`: {cnt}")

    lines.append("\n## Score Distribution")
    for bucket, cnt in report.get("score_histogram", {}).items():
        lines.append(f"- {bucket}: {cnt}")

    lines.append("\n## Store Count Distribution")
    for bucket, cnt in report.get("store_count_distribution", {}).items():
        lines.append(f"- {bucket} stores: {cnt}")

    lines.append("\n## Price Distribution (€)")
    for bucket, cnt in report.get("price_distribution", {}).items():
        lines.append(f"- €{bucket}: {cnt}")

    return "\n".join(lines)


def save_report(report: Dict, output_dir: str) -> Tuple[str, str]:
    """Save JSON and markdown report files. Returns (json_path, md_path)."""
    os.makedirs(output_dir, exist_ok=True)
    city_slug = report["city"].lower().replace(" ", "_")

    json_path = os.path.join(output_dir, f"{city_slug}_rubric.json")
    with open(json_path, "w") as f:
        json.dump(report, f, indent=2, default=str)

    md_path = os.path.join(output_dir, f"{city_slug}_rubric.md")
    with open(md_path, "w") as f:
        f.write(report_to_markdown(report))

    return json_path, md_path

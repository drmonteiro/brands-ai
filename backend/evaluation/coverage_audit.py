"""
Coverage Audit for Confeções Lança Prospector

Reads structured stage logs emitted by validation_node (stage_log calls)
and analyses rejected candidates at each stage to detect false negatives.

For each stage, samples rejected candidates, applies the rubric (with
partial data), and reports how many would have passed — the proxy for recall.
"""
import json
import os
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .rubric_evaluator import load_rubric, _normalise_brand, evaluate_brand, report_to_markdown


# ============================================================================
# Log parsing
# ============================================================================

STAGE_LOG_RE = re.compile(
    r"\[stage=(\S+)\]\s+\[city=([^\]]+)\]\s+\[candidates_in=(\d+)\]\s+\[candidates_out=(\d+)\](.*)"
)
EXTRA_KV_RE = re.compile(r"\[(\w+)=([^\]]*)\]")


def parse_stage_logs(log_text: str) -> List[Dict]:
    """Parse structured stage log lines into dicts."""
    entries = []
    for line in log_text.splitlines():
        m = STAGE_LOG_RE.search(line)
        if m:
            entry = {
                "stage": m.group(1),
                "city": m.group(2),
                "candidates_in": int(m.group(3)),
                "candidates_out": int(m.group(4)),
            }
            for km in EXTRA_KV_RE.finditer(m.group(5)):
                key, val = km.group(1), km.group(2)
                try:
                    entry[key] = int(val)
                except ValueError:
                    entry[key] = val
            entries.append(entry)
    return entries


def parse_stage_logs_from_file(path: str) -> List[Dict]:
    with open(path) as f:
        return parse_stage_logs(f.read())


# ============================================================================
# Leak analysis (without needing actual candidate data)
# ============================================================================

def compute_stage_retention(stage_entries: List[Dict], city: str) -> Dict:
    """
    Compute per-stage retention for a city from parsed stage log entries.
    Returns a dict mapping stage -> {candidates_in, candidates_out, dropped, retention_pct}.
    """
    city_entries = [e for e in stage_entries if e["city"].lower() == city.lower()]
    if not city_entries:
        return {}

    retention = {}
    for entry in city_entries:
        stage = entry["stage"]
        cin = entry["candidates_in"]
        cout = entry["candidates_out"]
        retention[stage] = {
            "candidates_in": cin,
            "candidates_out": cout,
            "dropped": cin - cout,
            "retention_pct": round(cout / cin * 100, 1) if cin > 0 else 0,
            **{k: v for k, v in entry.items() if k not in ("stage", "city", "candidates_in", "candidates_out")},
        }
    return retention


# ============================================================================
# Rubric-based false negative estimation on rejected candidates
# ============================================================================

def audit_rejected_candidates(
    rejected_candidates: List[Dict],
    rubric: Optional[Dict] = None,
    sample_size: int = 20,
) -> Dict:
    """
    Apply the rubric to a sample of rejected candidates.

    Args:
        rejected_candidates: List of candidate dicts (partial data is OK).
        rubric: Loaded rubric dict. Uses default if None.
        sample_size: Max candidates to evaluate per stage.

    Returns:
        Dict with counts of how many rejected candidates pass critical criteria.
    """
    if rubric is None:
        rubric = load_rubric()

    sample = rejected_candidates[:sample_size]
    total_sampled = len(sample)
    if total_sampled == 0:
        return {"sampled": 0, "would_pass_all_critical": 0, "pct_false_negative": 0}

    pass_all = 0
    partial_results = []
    for cand in sample:
        norm = _normalise_brand(cand)
        ev = evaluate_brand(norm, rubric)
        crit_statuses = [v["status"] for v in ev["critical"].values()]
        passes = all(s in ("pass", "unknown") for s in crit_statuses)
        if passes:
            pass_all += 1
        partial_results.append({
            "name": norm["name"],
            "passes_critical": passes,
            "critical_results": {k: v["status"] for k, v in ev["critical"].items()},
        })

    return {
        "sampled": total_sampled,
        "would_pass_all_critical": pass_all,
        "pct_false_negative": round(pass_all / total_sampled * 100, 1) if total_sampled else 0,
        "details": partial_results,
    }


# ============================================================================
# Full audit report
# ============================================================================

def generate_audit_report(
    stage_entries: List[Dict],
    city: str,
    per_stage_rejected: Optional[Dict[str, List[Dict]]] = None,
) -> Dict:
    """
    Generate a full coverage audit report for a city.

    Args:
        stage_entries: Parsed stage log entries (from parse_stage_logs).
        city: Target city name.
        per_stage_rejected: Optional dict mapping stage name -> list of rejected
            candidate dicts. If provided, rubric is applied to sample.

    Returns:
        Audit report dict.
    """
    retention = compute_stage_retention(stage_entries, city)

    rubric = load_rubric()
    false_neg_analysis = {}
    if per_stage_rejected:
        for stage, candidates in per_stage_rejected.items():
            false_neg_analysis[stage] = audit_rejected_candidates(candidates, rubric)

    biggest_leak_stage = None
    biggest_leak_drop = 0
    for stage, data in retention.items():
        if data["dropped"] > biggest_leak_drop:
            biggest_leak_drop = data["dropped"]
            biggest_leak_stage = stage

    return {
        "city": city,
        "timestamp": datetime.utcnow().isoformat(),
        "per_stage_retention": retention,
        "biggest_leak": {
            "stage": biggest_leak_stage,
            "dropped": biggest_leak_drop,
        },
        "false_negative_analysis": false_neg_analysis,
    }


def audit_report_to_markdown(report: Dict) -> str:
    """Convert audit report to markdown."""
    lines = [
        f"# Coverage Audit — {report['city']}",
        f"*Generated: {report.get('timestamp', 'N/A')}*\n",
        "## Per-Stage Retention",
        "| Stage | In | Out | Dropped | Retention |",
        "|-------|---:|----:|--------:|----------:|",
    ]
    for stage, data in report.get("per_stage_retention", {}).items():
        lines.append(
            f"| {stage} | {data['candidates_in']} | {data['candidates_out']} "
            f"| {data['dropped']} | {data['retention_pct']}% |"
        )

    leak = report.get("biggest_leak", {})
    if leak.get("stage"):
        lines.append(f"\n**Biggest leak:** `{leak['stage']}` dropped {leak['dropped']} candidates.\n")

    fn = report.get("false_negative_analysis", {})
    if fn:
        lines.append("## False Negative Analysis (rubric on rejected candidates)")
        for stage, data in fn.items():
            lines.append(
                f"\n### {stage}\n"
                f"- Sampled: {data['sampled']}\n"
                f"- Would pass all critical: {data['would_pass_all_critical']} "
                f"({data['pct_false_negative']}%)"
            )

    return "\n".join(lines)


def save_audit_report(report: Dict, output_dir: str) -> Tuple[str, str]:
    """Save JSON and markdown audit report. Returns (json_path, md_path)."""
    os.makedirs(output_dir, exist_ok=True)
    city_slug = report["city"].lower().replace(" ", "_")

    json_path = os.path.join(output_dir, f"{city_slug}_audit.json")
    with open(json_path, "w") as f:
        json.dump(report, f, indent=2, default=str)

    md_path = os.path.join(output_dir, f"{city_slug}_audit.md")
    with open(md_path, "w") as f:
        f.write(audit_report_to_markdown(report))

    return json_path, md_path

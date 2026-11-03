"""
Run the real enrichment, similarity, fit and gate on labelled brands, without saving
leads. Needs live API keys, and a database with the lanca_clients table.

    python -m evaluation.lead_quality_eval --sample golden --out report.json
    python -m evaluation.lead_quality_eval --sample clients --out report.json
"""

import argparse
import asyncio
import json
import os
import statistics
from pathlib import Path
from urllib.parse import urlparse
from typing import Any, Dict, List

import yaml
from exa_py import Exa

from data.lanca_clients import LANCA_CLIENTS
from services.lead_recheck import assess_brands
from services.linkedin_contacts import simplify_name

GOLDEN_PATH = Path(__file__).resolve().parent / "golden_leads.yaml"
GENERIC_NAME_WORDS = {"gmbh", "grupo", "bayertree", "espanolas", "sastrerias"}


def _site_matches_name(url: str, name: str) -> bool:
    host = simplify_name(urlparse(url).netloc)
    words = [w for w in simplify_name(name).split() if len(w) >= 4 and w not in GENERIC_NAME_WORDS]
    return bool(words) and all(w in host.replace(" ", "") for w in words)


async def _find_client_site(exa: Exa, client: Dict[str, Any]) -> Dict[str, Any]:
    name = client["name"]
    query = f"{name} {client.get('country', '')} menswear official website"
    results = (await asyncio.to_thread(exa.search, query, num_results=3, type="auto", category="company")).results
    # Search can return a different business, which tests nothing about the gate.
    url = next((r.url for r in results if _site_matches_name(r.url, name)), "")
    return {
        "name": name,
        "url": url,
        "country": client.get("country", ""),
        "known_stores": client.get("store_count"),
    }


def summarize(rows: List[Dict[str, Any]], brands: List[Dict[str, Any]]) -> Dict[str, Any]:
    results = []
    for row, brand in zip(rows, brands, strict=True):
        results.append({
            "name": row["name"],
            "extracted_name": brand.get("name"),
            "url": row["url"],
            "label": row.get("label"),
            "why": row.get("why"),
            "accepted": brand["_gate"]["accepted"],
            "code": brand["_gate"]["code"],
            "reason": brand["_gate"]["reason"],
            "category": brand.get("core_category"),
            "official": brand.get("is_official_site"),
            "evidence_ok": brand.get("suit_evidence_verified"),
            "level": brand.get("client_level"),
            "fit": brand.get("llm_fit_score"),
            "similarity": round(brand.get("similarity_score") or 0, 1),
            "price_status": brand.get("price_status"),
            "price_eur": brand.get("avg_suit_price_eur"),
            "price_source": brand.get("price_source_url"),
            "price_evidence": (brand.get("price_evidence") or [])[:2],
            "fit_reason": brand.get("llm_fit_reason"),
        })
    accepted = [r for r in results if r["accepted"]]
    labelled = [r for r in accepted if r["label"]]
    sims = [r["similarity"] for r in results]
    return {
        "total": len(results),
        "accepted": len(accepted),
        "good_among_accepted": sum(r["label"] == "good" for r in labelled),
        "bad_among_accepted": sum(r["label"] == "bad" for r in labelled),
        "good_rejected": sum(r["label"] == "good" and not r["accepted"] for r in results),
        "prices_confirmed": sum(r["price_status"] == "confirmed" for r in results),
        "similarity_median": statistics.median(sims) if sims else 0,
        "results": results,
    }


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", choices=["golden", "clients"], required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    if args.sample == "golden":
        golden = yaml.safe_load(GOLDEN_PATH.read_text())
        rows = [{**r, "label": label} for label in ("good", "bad") for r in golden[label]]
    else:
        exa = Exa(api_key=os.environ["EXA_API_KEY"])
        rows = [await _find_client_site(exa, c) for c in LANCA_CLIENTS]
        rows = [r for r in rows if r["url"]]

    report = summarize(rows, await assess_brands(rows))
    Path(args.out).write_text(json.dumps(report, indent=1, ensure_ascii=False, default=str))
    print(json.dumps({k: v for k, v in report.items() if k != "results"}, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())

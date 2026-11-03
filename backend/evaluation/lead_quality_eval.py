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

from agents.nodes import enrich as enrich_mod
from agents.nodes import persistence as persistence_mod
from data.lanca_clients import LANCA_CLIENTS
from services.lead_gate import evaluate_lead
from services.linkedin_contacts import simplify_name
from services.runtime_scoring import compute_runtime_final_score

GOLDEN_PATH = Path(__file__).resolve().parent / "golden_leads.yaml"
BATCH_SIZE = enrich_mod.ENRICH_BATCH_SIZE
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


async def evaluate_brands(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    working = enrich_mod._prepare_working_brands(
        [{"url": r["url"], "brand_name": r["name"], "title": r["name"], "text": "", "highlights": ""} for r in rows]
    )
    # The search result's text normally arrives from discovery. Here the site is known.
    exa = Exa(api_key=os.environ["EXA_API_KEY"])
    for brand in working:
        response = await asyncio.to_thread(
            exa.get_contents, [brand["url"]], text={"maxCharacters": enrich_mod.DISCOVERY_SLICE}
        )
        brand["text"] = next((r.text for r in response.results if getattr(r, "text", None)), "")

    contents = await enrich_mod._batch_fetch_exa_supplements(working)
    out: List[Dict[str, Any]] = []
    for start in range(0, len(working), BATCH_SIZE):
        batch, batch_contents = working[start:start + BATCH_SIZE], contents[start:start + BATCH_SIZE]
        extracted = await enrich_mod._extract_structured_batch(batch, batch_contents, "", "")
        for brand, row, content in zip(batch, extracted, batch_contents, strict=True):
            merged = enrich_mod._merge_extracted_into_brand(brand, row, brand)
            enrich_mod._apply_evidence(merged, row, content)
            merged["store_count"] = merged.get("_site_store_count") or 1
            out.append(merged)

    similar = await persistence_mod._find_similar_with_retries([persistence_mod._build_profile_text(b) for b in out])
    for start in range(0, len(out), persistence_mod.FIT_BATCH_SIZE):
        batch = out[start:start + persistence_mod.FIT_BATCH_SIZE]
        for brand, fit in zip(batch, await persistence_mod._llm_fit_assessment(batch, "")):
            brand.update(
                llm_fit_score=fit["fit_score"],
                client_level=fit["client_level"],
                closest_client=fit["closest_client"],
                llm_fit_reason=fit["fit_reason"],
            )
    for brand, matches, row in zip(out, similar, rows, strict=True):
        # Real clients are in the comparison table, and matching themselves proves nothing.
        others = [m for m in matches if m["name"] != row["name"]] or matches
        brand["similarity_score"] = persistence_mod._similarity_from_matches(others) if others else 0
        brand["similarity_failed"] = not others
        if row.get("known_stores"):
            brand["store_count"] = row["known_stores"]
        brand["final_score"] = compute_runtime_final_score(
            brand["similarity_score"], brand["llm_fit_score"], brand.get("avg_suit_price_eur") or 0, brand["store_count"]
        )[0]
        decision = evaluate_lead(brand)
        brand["_gate"] = {"accepted": decision.accepted, "code": decision.code, "reason": decision.reason}
    return out


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

    report = summarize(rows, await evaluate_brands(rows))
    Path(args.out).write_text(json.dumps(report, indent=1, ensure_ascii=False, default=str))
    print(json.dumps({k: v for k, v in report.items() if k != "results"}, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())

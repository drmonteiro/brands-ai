"""
Check saved leads against the quality gate. Nothing is deleted.

    # Report only: runs the real enrichment and writes a CSV. Changes nothing.
    python -m scripts.audit_existing_leads report --out audit.csv

    # After review, hide the prospect ids in a file (one per line). Reversible.
    python -m scripts.audit_existing_leads hide --ids approved_ids.txt
    python -m scripts.audit_existing_leads unhide --ids approved_ids.txt
"""

import argparse
import asyncio
import csv
from pathlib import Path

from evaluation.lead_quality_eval import evaluate_brands
from services.postgres import PostgresManager

REPORT_BATCH_SIZE = 12


async def report(out: str, city: str | None, limit: int | None) -> None:
    pool = await PostgresManager.get_pool()
    query = "SELECT id, name, website_url, city, country FROM prospects WHERE quality_status = 'active'"
    args = []
    if city:
        args.append(city.lower())
        query += " AND city = $1"
    query += " ORDER BY city, name"
    async with pool.acquire() as conn:
        leads = [dict(r) for r in await conn.fetch(query, *args)]
    leads = leads[:limit] if limit else leads

    with open(out, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "city", "name", "url", "keep", "code", "reason", "price_eur", "price_status", "fit_reason"])
        for start in range(0, len(leads), REPORT_BATCH_SIZE):
            batch = leads[start:start + REPORT_BATCH_SIZE]
            rows = [{"name": r["name"], "url": r["website_url"], "country": r["country"]} for r in batch]
            for lead, brand in zip(batch, await evaluate_brands(rows)):
                writer.writerow([
                    lead["id"], lead["city"], lead["name"], lead["website_url"],
                    brand["_gate"]["accepted"], brand["_gate"]["code"], brand["_gate"]["reason"],
                    brand.get("avg_suit_price_eur"), brand.get("price_status"), brand.get("llm_fit_reason"),
                ])
            f.flush()
            print(f"{min(start + REPORT_BATCH_SIZE, len(leads))}/{len(leads)}", flush=True)


async def set_status(ids_file: str, status: str) -> None:
    ids = [line.strip() for line in Path(ids_file).read_text().splitlines() if line.strip()]
    pool = await PostgresManager.get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE prospects SET quality_status = $1, updated_at = CURRENT_TIMESTAMP WHERE id = ANY($2::text[])",
            status,
            ids,
        )
    print(f"{result} ({status})")


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    report_parser = commands.add_parser("report")
    report_parser.add_argument("--out", required=True)
    report_parser.add_argument("--city")
    report_parser.add_argument("--limit", type=int)
    for name in ("hide", "unhide"):
        commands.add_parser(name).add_argument("--ids", required=True)
    args = parser.parse_args()

    if args.command == "report":
        await report(args.out, args.city, args.limit)
    else:
        await set_status(args.ids, "hidden" if args.command == "hide" else "active")


if __name__ == "__main__":
    asyncio.run(main())

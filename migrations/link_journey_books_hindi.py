"""
One-shot migration: link journey_books for the Hindi journey rows created by
migrate_journeys_hindi.py.

Source: journey_automation/jsons_hindi/*.json -- the Hindi counterpart of the
original bootstrap jsons/ folder (matched migrate_journeys_json.py uses for
English). Unlike journeys/hindi/*.json, these files carry a summary_id per
book (e.g. "SUM-448"), the same linear_id used by the English book -- the
Hindi book summary lives under that same linear_id with language='hindi' in
the summaries table.

For each file:
  - linear_identifier -> matches an existing journeys row (language='hindi')
  - each books[].summary_id -> matches an existing summaries row
    (linear_id=summary_id, language='hindi')
  - inserts one journey_books row per resolved book, in book order

Idempotent: ON CONFLICT (journey_id, summary_id) DO NOTHING.
"""

import asyncio
import json
import os
import re
from pathlib import Path

import asyncpg

JSONS_HINDI_DIR = Path("/home/saurav/kitab/auto_pipeline/journey_automation/jsons_hindi")


def _conn_str() -> str:
    conn_str = os.environ.get("NEON_CONNECTION_STRING") or os.environ.get("DATABASE_URL")
    if not conn_str:
        for line in open(Path(__file__).resolve().parents[1] / ".env"):
            if line.startswith("NEON_CONNECTION_STRING"):
                conn_str = line.split("=", 1)[1].strip().strip('"')
                break
    if not conn_str:
        raise RuntimeError("NEON_CONNECTION_STRING/DATABASE_URL not set")
    conn_str = conn_str.replace("postgresql+asyncpg://", "postgresql://")
    return re.sub(r"\?.*$", "", conn_str)


async def migrate() -> None:
    conn = await asyncpg.connect(_conn_str())
    linked = skipped_link_exists = warn_no_summary = skipped_no_journey = 0
    try:
        for path in sorted(JSONS_HINDI_DIR.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            linear_id = (data.get("linear_identifier") or "").strip()
            if not linear_id:
                print(f"SKIP (no linear_identifier): {path.name}")
                continue

            journey_id = await conn.fetchval(
                "SELECT id FROM journeys WHERE linear_id = $1 AND language = 'hindi'",
                linear_id,
            )
            if not journey_id:
                print(f"SKIP (no Hindi journey row for {linear_id}): {path.name}")
                skipped_no_journey += 1
                continue

            for order, book in enumerate(data.get("books") or []):
                summary_linear_id = (book.get("summary_id") or "").strip()
                if not summary_linear_id:
                    print(f"  WARN (book has no summary_id): {path.name} book #{order}")
                    warn_no_summary += 1
                    continue

                summary_id = await conn.fetchval(
                    "SELECT id FROM summaries WHERE linear_id = $1 AND language = 'hindi'",
                    summary_linear_id,
                )
                if not summary_id:
                    print(f"  WARN (no Hindi summary for {summary_linear_id}): {path.name}")
                    warn_no_summary += 1
                    continue

                result = await conn.execute(
                    """
                    INSERT INTO journey_books (journey_id, summary_id, book_order, search_title, summary_title)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (journey_id, summary_id) DO NOTHING
                    """,
                    journey_id,
                    summary_id,
                    order,
                    book.get("search_title"),
                    book.get("summary_title"),
                )
                if result.endswith(" 0"):
                    skipped_link_exists += 1
                else:
                    linked += 1

            print(f"OK: {linear_id} — {data.get('journey_title')} ({len(data.get('books') or [])} books)")
    finally:
        await conn.close()

    print(
        f"\nDone. linked={linked} "
        f"skipped_existing_link={skipped_link_exists} "
        f"warn_no_summary_match={warn_no_summary} "
        f"skipped_no_journey_row={skipped_no_journey}"
    )


if __name__ == "__main__":
    asyncio.run(migrate())

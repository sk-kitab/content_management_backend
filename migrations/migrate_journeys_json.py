#!/usr/bin/env python3
"""
One-shot migration: read journey JSON files → insert into journeys + journey_books tables.

Usage:
    cd /home/saurav/kitab/content_management_system
    python backend/migrations/migrate_journeys_json.py

Requires:
    NEON_CONNECTION_STRING or DATABASE_URL env var set.
    Run AFTER 003_journeys.sql migration.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

import asyncpg

JSONS_DIR = Path("/home/saurav/kitab/auto_pipeline/journey_automation/jsons")

STATUS_MAP = {
    "Source": "source",
    "Creation": "creation",
    "Push to Linear": "push_to_linear",
}


def _db_url() -> str:
    url = os.getenv("NEON_CONNECTION_STRING") or os.getenv("DATABASE_URL")
    if not url:
        sys.exit("ERROR: set NEON_CONNECTION_STRING or DATABASE_URL")
    return url.replace("postgresql+asyncpg://", "postgresql://").split("?")[0]


async def migrate():
    conn = await asyncpg.connect(_db_url(), ssl="require")
    json_files = sorted(JSONS_DIR.glob("*.json"))
    print(f"Found {len(json_files)} JSON files")

    inserted = 0
    skipped = 0

    for path in json_files:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)

        journey_title = data.get("journey_title", "").strip()
        if not journey_title:
            print(f"  SKIP {path.name}: no journey_title")
            skipped += 1
            continue

        # Idempotent: skip if already migrated
        existing = await conn.fetchval(
            "SELECT id FROM journeys WHERE journey_title = $1", journey_title
        )
        if existing:
            print(f"  SKIP {path.name}: already in DB (id={existing})")
            skipped += 1
            continue

        raw_status = data.get("status", "Source")
        status = STATUS_MAP.get(raw_status, "source")

        journey_id = await conn.fetchval(
            """
            INSERT INTO journeys (
                linear_id, linear_issue_id, linear_assignee,
                journey_title, type, transformation, categories, theme,
                heartfulness_text, source_csv, row_number,
                status, output_sections
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
            RETURNING id
            """,
            data.get("linear_identifier"),
            data.get("linear_issue_id"),
            data.get("linear_assignee"),
            journey_title,
            data.get("type"),
            data.get("transformation"),
            data.get("categories"),
            data.get("theme"),
            data.get("heartfulness_text"),
            data.get("source_csv"),
            data.get("row_number"),
            status,
            json.dumps(data.get("Output")) if data.get("Output") else None,
        )

        # Resolve book summary_ids via summaries.linear_id
        books = data.get("books", [])
        for order, book in enumerate(books):
            summary_linear_id = book.get("summary_id")
            if not summary_linear_id:
                continue
            summary_id = await conn.fetchval(
                "SELECT id FROM summaries WHERE linear_id = $1 AND language = 'english' LIMIT 1",
                summary_linear_id,
            )
            if summary_id:
                await conn.execute(
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
            else:
                print(f"    WARN: summary not found for {summary_linear_id} in {path.name}")

        print(f"  OK  {path.name} → journey_id={journey_id} (status={status})")
        inserted += 1

    await conn.close()
    print(f"\nDone. Inserted: {inserted}, Skipped: {skipped}")


if __name__ == "__main__":
    asyncio.run(migrate())

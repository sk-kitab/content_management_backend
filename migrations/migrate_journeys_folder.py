#!/usr/bin/env python3
"""
Migration: read journey JSON files from journeys/ folder → update journeys table.

Updates output_sections, tagline, overview, cover_page, duration for all
English journeys matched by linear_id. Skips any entry whose id is 'JOU-NEW'.
Scoped to language='english' -- see migrate_journeys_hindi.py for the Hindi
counterpart; do not drop the language filter or this will also overwrite
the Hindi rows sharing the same linear_id.

Usage:
    cd /home/saurav/kitab/content_management_system
    python backend/migrations/migrate_journeys_folder.py
"""

import asyncio
import json
import os
import sys
from pathlib import Path

import asyncpg

JOURNEYS_DIR = Path("/home/saurav/kitab/auto_pipeline/journey_automation/journeys")


def _db_url() -> str:
    url = os.getenv("NEON_CONNECTION_STRING") or os.getenv("DATABASE_URL", "")
    if not url:
        sys.exit("ERROR: set NEON_CONNECTION_STRING or DATABASE_URL")
    return url.replace("postgresql+asyncpg://", "postgresql://").split("?")[0]


async def migrate():
    conn = await asyncpg.connect(_db_url(), ssl="require")

    # Run schema migration first
    await conn.execute("""
        ALTER TABLE journeys
            ADD COLUMN IF NOT EXISTS tagline    TEXT,
            ADD COLUMN IF NOT EXISTS overview   TEXT,
            ADD COLUMN IF NOT EXISTS cover_page TEXT,
            ADD COLUMN IF NOT EXISTS duration   INTEGER
    """)
    print("Schema columns ensured.")

    json_files = sorted(f for f in JOURNEYS_DIR.glob("*.json") if f.parent == JOURNEYS_DIR)
    print(f"Found {len(json_files)} journey files in journeys/\n")

    updated = skipped = not_found = 0

    for path in json_files:
        d = json.load(open(path, encoding="utf-8"))

        linear_id = d.get("id", "").strip()
        if not linear_id or linear_id == "JOU-NEW":
            print(f"  SKIP {path.name}: id={linear_id!r}")
            skipped += 1
            continue

        existing_id = await conn.fetchval(
            "SELECT id FROM journeys WHERE linear_id = $1 AND language = 'english'", linear_id
        )
        if not existing_id:
            print(f"  MISS {path.name}: linear_id={linear_id} not in DB")
            not_found += 1
            continue

        content = d.get("content")

        await conn.execute(
            """
            UPDATE journeys SET
                output_sections = $1,
                tagline         = $2,
                overview        = $3,
                cover_page      = $4,
                duration        = $5
            WHERE linear_id = $6 AND language = 'english'
            """,
            json.dumps(content) if content else None,
            d.get("tagline"),
            d.get("overview"),
            d.get("cover_page"),
            d.get("duration"),
            linear_id,
        )
        print(f"  OK  {path.name} → linear_id={linear_id}")
        updated += 1

    await conn.close()
    print(f"\nDone. Updated: {updated}, Skipped: {skipped}, Not found: {not_found}")


if __name__ == "__main__":
    asyncio.run(migrate())

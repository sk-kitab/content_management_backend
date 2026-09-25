"""
One-shot migration: load Hindi journeys from journey_automation/journeys/hindi/
into the journeys table as language='hindi' rows, alongside their existing
English (language='english') counterparts under the same linear_id.

Run after 005_journeys_language.sql has been applied.

Each hindi/*.json carries its own title, categories, theme, transformation,
heartfulness_text, output content, tagline, overview, cover_page, and
duration -- but not the Linear/production bookkeeping fields (type,
status, source_csv, row_number, linear_issue_id, linear_assignee). Those are
inherited from the existing English row for the same linear_id, since they
describe the same underlying Linear issue, not the language.

Book links (journey_books) are intentionally NOT created here: the hindi
files embed each book's full final_summary inline rather than referencing a
summaries row by id, and these journeys already ship complete, pre-authored
narration content (output_sections) -- there is nothing left to link for
generate-narration to regenerate.

Idempotent: re-running skips rows that already exist for (linear_id, hindi).
"""

import asyncio
import json
import os
import re
from pathlib import Path

import asyncpg

JOURNEYS_DIR = Path("/home/saurav/kitab/auto_pipeline/journey_automation/journeys")
HINDI_DIR = JOURNEYS_DIR / "hindi"


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
    inserted = skipped_exists = skipped_no_english = skipped_no_id = 0
    try:
        for path in sorted(HINDI_DIR.glob("*.json")):
            data = json.loads(path.read_text(encoding="utf-8"))
            linear_id = (data.get("id") or "").strip()
            if not linear_id or linear_id == "JOU-NEW":
                print(f"SKIP (no linear_id): {path.name}")
                skipped_no_id += 1
                continue

            english = await conn.fetchrow(
                """
                SELECT type, status, source_csv, row_number,
                       linear_issue_id, linear_assignee
                FROM journeys
                WHERE linear_id = $1 AND language = 'english'
                """,
                linear_id,
            )
            if not english:
                print(f"SKIP (no matching English row for {linear_id}): {path.name}")
                skipped_no_english += 1
                continue

            existing = await conn.fetchval(
                "SELECT id FROM journeys WHERE linear_id = $1 AND language = 'hindi'",
                linear_id,
            )
            if existing:
                print(f"SKIP (already exists): {linear_id} — {data.get('title')}")
                skipped_exists += 1
                continue

            await conn.execute(
                """
                INSERT INTO journeys (
                    linear_id, linear_issue_id, linear_assignee, language,
                    journey_title, type, transformation, categories, theme,
                    heartfulness_text, source_csv, row_number, status,
                    output_sections, tagline, overview, cover_page, duration
                ) VALUES (
                    $1, $2, $3, 'hindi',
                    $4, $5, $6, $7, $8,
                    $9, $10, $11, $12,
                    $13, $14, $15, $16, $17
                )
                """,
                linear_id,
                english["linear_issue_id"],
                english["linear_assignee"],
                data.get("title") or "",
                english["type"],
                data.get("transformation"),
                data.get("categories"),
                data.get("theme"),
                data.get("heartfulness_text"),
                english["source_csv"],
                english["row_number"],
                english["status"],
                json.dumps(data.get("content")) if data.get("content") is not None else None,
                data.get("tagline"),
                data.get("overview"),
                data.get("cover_page"),
                data.get("duration"),
            )
            print(f"INSERTED: {linear_id} — {data.get('title')}")
            inserted += 1
    finally:
        await conn.close()

    print(
        f"\nDone. inserted={inserted} "
        f"skipped_existing={skipped_exists} "
        f"skipped_no_english_match={skipped_no_english} "
        f"skipped_no_linear_id={skipped_no_id}"
    )


if __name__ == "__main__":
    asyncio.run(migrate())

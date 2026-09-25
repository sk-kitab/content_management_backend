"""
One-shot data fix: give Hindi journeys the same cover_page as their English
counterpart (same underlying artwork, no translation needed), and backfill
tagline/overview with Hindi translations for the rows that source data
never provided them for.

- cover_page: copied from the English row for every Hindi row (safe to
  always set -- the 6 rows that already had a Hindi cover_page had the
  exact same URL as English anyway, confirmed before running this).
- tagline / overview: applied only from translations.json, which covers
  the 54 Hindi journeys that had neither -- the 6 that already shipped
  with a human/source-provided Hindi tagline+overview are left untouched.

Idempotent: re-running just reassigns the same values.
"""

import asyncio
import json
import os
import re
from pathlib import Path

import asyncpg

TRANSLATIONS_PATH = Path(__file__).resolve().parent / "hindi_tagline_overview.json"


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
    translations = json.loads(TRANSLATIONS_PATH.read_text(encoding="utf-8"))
    conn = await asyncpg.connect(_conn_str())
    covers_set = translated = 0
    try:
        english_rows = await conn.fetch(
            "SELECT linear_id, cover_page FROM journeys WHERE language = 'english'"
        )
        for row in english_rows:
            if not row["cover_page"]:
                continue
            result = await conn.execute(
                "UPDATE journeys SET cover_page = $1 WHERE linear_id = $2 AND language = 'hindi'",
                row["cover_page"],
                row["linear_id"],
            )
            if not result.endswith(" 0"):
                covers_set += 1

        for linear_id, t in translations.items():
            result = await conn.execute(
                "UPDATE journeys SET tagline = $1, overview = $2 WHERE linear_id = $3 AND language = 'hindi'",
                t["tagline"],
                t["overview"],
                linear_id,
            )
            if not result.endswith(" 0"):
                translated += 1
            else:
                print(f"  WARN: no Hindi row updated for {linear_id}")
    finally:
        await conn.close()

    print(f"Done. cover_page set on {covers_set} rows, tagline/overview set on {translated} rows.")


if __name__ == "__main__":
    asyncio.run(migrate())

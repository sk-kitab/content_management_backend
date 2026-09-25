"""
One-shot data fix: some journeys' output_sections carry a stray, empty
leading section -- a leftover from the content-generation pass (title is
junk placeholder text like "```markdown\n```", "शीर्षक" ("title"), or
"कृपया अनुवाद के लिए शीर्षक प्रदान करें।" ("please provide a title for
translation"), and content is always {}). Confirmed to hit the exact same
19 linear_ids in both languages -- a generation-run artifact, not a
language-specific issue.

This drops that empty leading section and renumbers the remaining sections
starting at "1", for every journey (any language) where the section keyed
lowest is empty. Confirmed non-destructive: every affected section's
content is an empty dict, never hiding real subsections.

Idempotent: only touches a row if its lowest-numbered section is empty.
Re-run any time output_sections is refreshed from source (e.g. after
migrate_journeys_folder.py or migrate_journeys_hindi.py).
"""

import asyncio
import json
import os
import re
from pathlib import Path

import asyncpg


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


def _is_empty_section(sec) -> bool:
    if not isinstance(sec, dict):
        return True
    content = sec.get("content")
    return not content


async def migrate() -> None:
    conn = await asyncpg.connect(_conn_str())
    fixed = skipped = 0
    try:
        rows = await conn.fetch(
            "SELECT id, linear_id, language, journey_title, output_sections FROM journeys "
            "WHERE output_sections IS NOT NULL"
        )
        for row in rows:
            sections = row["output_sections"]
            if isinstance(sections, str):
                sections = json.loads(sections)
            if not isinstance(sections, dict) or not sections:
                continue

            keys = [k for k in sections if k.isdigit()]
            if not keys:
                continue
            keys_sorted = sorted(keys, key=int)
            first_key = keys_sorted[0]

            if not _is_empty_section(sections[first_key]):
                continue

            dropped_title = sections[first_key].get("title")
            remaining = [sections[k] for k in keys_sorted[1:]]
            renumbered = {str(i + 1): sec for i, sec in enumerate(remaining)}
            # keep any non-numeric keys untouched, just in case
            for k, v in sections.items():
                if not k.isdigit():
                    renumbered[k] = v

            await conn.execute(
                "UPDATE journeys SET output_sections = $1 WHERE id = $2",
                json.dumps(renumbered),
                row["id"],
            )
            print(
                f"FIXED: {row['linear_id']} ({row['language']}) — {row['journey_title']} "
                f"— dropped section 1 (title={dropped_title!r}), now {len(renumbered)} sections"
            )
            fixed += 1
    finally:
        await conn.close()

    print(f"\nDone. fixed={fixed}")


if __name__ == "__main__":
    asyncio.run(migrate())

import sqlite3, psycopg2, os, json
from datetime import datetime

SQLITE_PATH = os.path.join(os.path.dirname(__file__), "../../local_summaries.db")
PG_DSN = os.environ["DATABASE_URL"]

STATUS_MAP = {
    "Source": "source",
    "voice text generated": "voice_text",
    "voice generated": "voice",
    "Uploaded": "voice",
}

INSERT_SQL = """
    INSERT INTO summaries (
        linear_id, language, title, category, book_path,
        final_summary, summary_chapters, top_150,
        voice_status, voice_id, voice_name,
        audio_url, supabase_uploaded,
        average_rating, rating_count, review_count
    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    ON CONFLICT (linear_id, language) DO UPDATE SET
        voice_status = EXCLUDED.voice_status,
        audio_url    = EXCLUDED.audio_url,
        updated_at   = NOW()
"""

BATCH_SIZE = 100


def build_params(r):
    summary_chapters = r["summary_chapters"]
    if summary_chapters and isinstance(summary_chapters, str):
        try:
            summary_chapters = json.loads(summary_chapters)
        except Exception:
            summary_chapters = None

    voice_status = STATUS_MAP.get(r["voice_status"] or "", "source")

    return (
        r["linear_id"], r["language"] or "english",
        r["title"], r["category"], r["book_path"],
        r["final_summary"],
        json.dumps(summary_chapters) if summary_chapters else None,
        bool(r["top_150"]),
        voice_status,
        r["voice_id"], r["voice_name"],
        r["audio_url"], bool(r["supabase_uploaded"]),
        r["average_rating"], r["rating_count"] or 0, r["review_count"] or 0,
    )


def migrate():
    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    sqlite_conn.row_factory = sqlite3.Row

    rows = sqlite_conn.execute("SELECT * FROM summaries").fetchall()
    sqlite_conn.close()

    total = len(rows)
    migrated = 0

    for batch_start in range(0, total, BATCH_SIZE):
        batch = rows[batch_start:batch_start + BATCH_SIZE]
        pg_conn = psycopg2.connect(PG_DSN)
        try:
            cur = pg_conn.cursor()
            for r in batch:
                cur.execute(INSERT_SQL, build_params(r))
            pg_conn.commit()
            migrated += len(batch)
            print(f"Progress: {migrated}/{total}")
        finally:
            pg_conn.close()

    print(f"Migrated {migrated} rows total")


if __name__ == "__main__":
    migrate()

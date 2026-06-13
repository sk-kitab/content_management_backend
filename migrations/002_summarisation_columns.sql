-- Add summarisation pipeline columns to summaries table
ALTER TABLE summaries
    ADD COLUMN IF NOT EXISTS summarisation_status VARCHAR,
    ADD COLUMN IF NOT EXISTS copyright_report JSONB,
    ADD COLUMN IF NOT EXISTS copyright_revised_summary TEXT,
    ADD COLUMN IF NOT EXISTS pdf_supabase_path TEXT;

-- Index for fast kanban queries by summarisation_status
CREATE INDEX IF NOT EXISTS idx_summaries_summarisation_status
    ON summaries(summarisation_status);

-- 004_journeys_enrich.sql
-- Add rich metadata columns populated from journeys/ folder

ALTER TABLE journeys
    ADD COLUMN IF NOT EXISTS tagline    TEXT,
    ADD COLUMN IF NOT EXISTS overview   TEXT,
    ADD COLUMN IF NOT EXISTS cover_page TEXT,
    ADD COLUMN IF NOT EXISTS duration   INTEGER;

-- 005_journeys_language.sql
-- Add a language column to journeys, mirroring summaries.language, so a
-- localized journey (e.g. Hindi) can exist alongside its English original
-- under the same linear_id.

ALTER TABLE journeys
    ADD COLUMN IF NOT EXISTS language TEXT NOT NULL DEFAULT 'english';

DROP INDEX IF EXISTS idx_journeys_linear_id;

CREATE UNIQUE INDEX IF NOT EXISTS idx_journeys_linear_id
    ON journeys (linear_id, language) WHERE linear_id IS NOT NULL;

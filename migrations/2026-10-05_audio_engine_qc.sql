-- v3 voice pipeline: per-summary audio engine + QC report
-- (docs/superpowers/specs/2026-10-05-v3-voice-pipeline-design.md)
-- Apply BEFORE deploying the backend that maps these columns.
ALTER TABLE summaries ADD COLUMN IF NOT EXISTS audio_engine text NOT NULL DEFAULT 'legacy';
ALTER TABLE summaries ADD COLUMN IF NOT EXISTS audio_qc_report jsonb;

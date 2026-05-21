-- backend/migrations/001_initial.sql

CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE summaries (
    id                      SERIAL PRIMARY KEY,
    linear_id               TEXT NOT NULL,
    language                TEXT NOT NULL DEFAULT 'english',

    -- Book metadata
    title                   TEXT NOT NULL,
    author                  TEXT,
    category                TEXT,
    book_path               TEXT,
    top_150                 BOOLEAN DEFAULT FALSE,

    -- Summary content
    initial_summary         TEXT,
    final_summary           TEXT,
    summary_chapters        JSONB,

    -- Hindi specific (populated for language='hindi' rows)
    hindi_title             TEXT,
    hindi_author            TEXT,
    hindi_summary           TEXT,
    hindi_chapters          JSONB,
    hindi_improved          BOOLEAN DEFAULT FALSE,
    hindi_restructured      BOOLEAN DEFAULT FALSE,

    -- Copyright / processing metadata
    status                  TEXT DEFAULT 'draft',
    copyright_status        TEXT,
    violations_count        INTEGER DEFAULT 0,
    restructured            BOOLEAN DEFAULT FALSE,

    -- Kanban stage: 'source' | 'voice_text' | 'voice'
    voice_status            TEXT DEFAULT 'source',
    voice_id                TEXT,
    voice_name              TEXT,
    voice_text_chapters     JSONB,

    -- Audio output
    audio_url               TEXT,
    audio_chapter_urls      JSONB,
    supabase_uploaded       BOOLEAN DEFAULT FALSE,
    is_uploaded             BOOLEAN DEFAULT FALSE,

    -- Ratings aggregates
    average_rating          REAL,
    rating_count            INTEGER DEFAULT 0,
    review_count            INTEGER DEFAULT 0,

    -- Timestamps
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW(),
    voice_text_generated_at TIMESTAMPTZ,
    audio_generated_at      TIMESTAMPTZ,
    uploaded_at             TIMESTAMPTZ,

    UNIQUE (linear_id, language)
);

CREATE TABLE reviews (
    id                  SERIAL PRIMARY KEY,
    linear_id           TEXT NOT NULL,
    language            TEXT NOT NULL DEFAULT 'english',
    rating              REAL,
    is_verified         BOOLEAN DEFAULT FALSE,
    reviewer_id         TEXT,
    feedback_details    JSONB,
    assignment_status   TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE pipeline_jobs (
    id           SERIAL PRIMARY KEY,
    linear_id    TEXT NOT NULL,
    language     TEXT NOT NULL,
    job_type     TEXT NOT NULL,
    status       TEXT DEFAULT 'pending',
    error        TEXT,
    started_at   TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

CREATE TRIGGER summaries_updated_at
    BEFORE UPDATE ON summaries
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Indexes
CREATE INDEX idx_summaries_voice_status ON summaries(voice_status);
CREATE INDEX idx_summaries_category ON summaries(category);
CREATE INDEX idx_summaries_language ON summaries(language);
CREATE INDEX idx_summaries_top_150 ON summaries(top_150) WHERE top_150 = TRUE;
CREATE INDEX idx_summaries_search ON summaries USING gin(
    to_tsvector('english', coalesce(title,'') || ' ' || coalesce(linear_id,''))
);

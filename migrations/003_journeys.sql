-- 003_journeys.sql

CREATE TABLE journeys (
    id                      SERIAL PRIMARY KEY,
    linear_id               TEXT,                          -- JOU-69
    linear_issue_id         TEXT,                          -- UUID from Linear
    linear_assignee         TEXT,

    journey_title           TEXT NOT NULL,
    type                    TEXT,
    transformation          TEXT,
    categories              TEXT,
    theme                   TEXT,
    heartfulness_text       TEXT,
    source_csv              TEXT,
    row_number              INTEGER,

    status                  TEXT DEFAULT 'source',         -- source | creation | push_to_linear
    narration_text          TEXT,
    output_sections         JSONB,                         -- raw Output dict from JSON files

    created_at              TIMESTAMPTZ DEFAULT now(),
    updated_at              TIMESTAMPTZ DEFAULT now(),
    narration_generated_at  TIMESTAMPTZ,
    uploaded_at             TIMESTAMPTZ
);

CREATE TABLE journey_books (
    id              SERIAL PRIMARY KEY,
    journey_id      INTEGER NOT NULL REFERENCES journeys(id) ON DELETE CASCADE,
    summary_id      INTEGER NOT NULL REFERENCES summaries(id),
    book_order      INTEGER NOT NULL DEFAULT 0,
    search_title    TEXT,
    summary_title   TEXT,
    UNIQUE (journey_id, summary_id)
);

CREATE INDEX idx_journeys_status    ON journeys(status);
CREATE INDEX idx_journeys_linear_id ON journeys(linear_id);
CREATE INDEX idx_journey_books_jid  ON journey_books(journey_id);

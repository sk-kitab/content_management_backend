# backend/schemas.py
from __future__ import annotations
from datetime import datetime
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict

VOICE_STATUSES = Literal["source", "voice_text", "voice"]

class SummaryCard(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    linear_id: str
    language: str
    title: str
    author: str | None
    category: str | None
    voice_status: str
    voice_name: str | None
    top_150: bool
    average_rating: float | None
    review_count: int
    audio_url: str | None
    summarisation_status: str | None = None
    pdf_supabase_path: str | None = None

class SummaryDetail(SummaryCard):
    initial_summary: str | None
    final_summary: str | None
    summary_chapters: Any
    hindi_title: str | None
    hindi_summary: str | None
    hindi_chapters: Any
    voice_id: str | None
    voice_text_chapters: Any
    audio_chapter_urls: Any
    created_at: datetime
    updated_at: datetime
    voice_text_generated_at: datetime | None
    audio_generated_at: datetime | None
    uploaded_at: datetime | None

class SummaryPatch(BaseModel):
    voice_status: VOICE_STATUSES | None = None
    voice_name: str | None = None
    voice_id: str | None = None
    audio_url: str | None = None

class KanbanColumn(BaseModel):
    status: str
    count: int
    items: list[SummaryCard]

class KanbanBoard(BaseModel):
    source: KanbanColumn
    voice_text: KanbanColumn
    voice: KanbanColumn

class JobCreate(BaseModel):
    linear_id: str
    language: str
    job_type: Literal["voice_text", "audio", "upload"]

class JobStatus(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    linear_id: str
    language: str
    job_type: str
    status: str
    error: str | None
    created_at: datetime
    completed_at: datetime | None

class ReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    linear_id: str
    language: str
    rating: float | None
    is_verified: bool
    reviewer_id: str | None
    feedback_details: Any
    assignment_status: str | None
    created_at: datetime


class SupabaseReviewOut(BaseModel):
    id: str
    assignment_id: str
    reviewer_id: str | None
    rating: int | None
    is_verified: bool
    created_at: datetime
    feedback_details: Any
    assignment_status: str | None
    iteration_count: int | None


class ReviewStats(BaseModel):
    month: str
    total_reviewed: int
    approved: int
    requested_changes: int
    average_rating: float | None

class FilterParams(BaseModel):
    language: str = "english"
    category: str | None = None
    voice_name: str | None = None
    top_150: bool = False
    search: str | None = None

JOURNEY_STATUSES = Literal["source", "creation", "push_to_linear"]

class JourneyBookRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    summary_id: int
    book_order: int
    search_title: str | None
    summary_title: str | None

class JourneyCard(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    linear_id: str | None
    journey_title: str
    type: str | None = None
    transformation: str | None = None
    categories: str | None = None
    theme: str | None = None
    status: str
    linear_assignee: str | None = None

class JourneyDetail(JourneyCard):
    linear_issue_id: str | None
    heartfulness_text: str | None
    source_csv: str | None
    row_number: int | None
    narration_text: str | None
    output_sections: Any
    books: list[JourneyBookRef] = []
    created_at: datetime
    updated_at: datetime
    narration_generated_at: datetime | None
    uploaded_at: datetime | None

class JourneyCreate(BaseModel):
    linear_id: str | None = None
    linear_issue_id: str | None = None
    linear_assignee: str | None = None
    journey_title: str
    type: str | None = None
    transformation: str | None = None
    categories: str | None = None
    theme: str | None = None
    heartfulness_text: str | None = None
    source_csv: str | None = None
    row_number: int | None = None
    status: JOURNEY_STATUSES = "source"
    output_sections: Any = None
    book_summary_ids: list[int] = []

class JourneyPatch(BaseModel):
    status: JOURNEY_STATUSES | None = None
    narration_text: str | None = None
    output_sections: Any = None
    linear_id: str | None = None
    linear_issue_id: str | None = None
    uploaded_at: datetime | None = None

class JourneyKanbanColumn(BaseModel):
    status: str
    count: int
    items: list[JourneyCard]

class JourneyKanbanBoard(BaseModel):
    source: JourneyKanbanColumn
    creation: JourneyKanbanColumn
    push_to_linear: JourneyKanbanColumn

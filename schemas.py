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

class FilterParams(BaseModel):
    language: str = "english"
    category: str | None = None
    voice_name: str | None = None
    top_150: bool = False
    search: str | None = None

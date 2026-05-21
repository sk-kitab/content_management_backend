# backend/models.py
from datetime import datetime
from sqlalchemy import String, Boolean, Integer, Float, DateTime, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from source.database import Base

class Summary(Base):
    __tablename__ = "summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    linear_id: Mapped[str] = mapped_column(String, nullable=False)
    language: Mapped[str] = mapped_column(String, nullable=False, default="english")

    title: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String)
    book_path: Mapped[str | None] = mapped_column(Text)
    top_150: Mapped[bool] = mapped_column(Boolean, default=False)

    initial_summary: Mapped[str | None] = mapped_column(Text)
    final_summary: Mapped[str | None] = mapped_column(Text)
    summary_chapters: Mapped[dict | None] = mapped_column(JSONB)

    hindi_title: Mapped[str | None] = mapped_column(Text)
    hindi_author: Mapped[str | None] = mapped_column(Text)
    hindi_summary: Mapped[str | None] = mapped_column(Text)
    hindi_chapters: Mapped[dict | None] = mapped_column(JSONB)
    hindi_improved: Mapped[bool] = mapped_column(Boolean, default=False)
    hindi_restructured: Mapped[bool] = mapped_column(Boolean, default=False)

    status: Mapped[str | None] = mapped_column(String, default="draft")
    copyright_status: Mapped[str | None] = mapped_column(String)
    violations_count: Mapped[int] = mapped_column(Integer, default=0)
    restructured: Mapped[bool] = mapped_column(Boolean, default=False)

    voice_status: Mapped[str] = mapped_column(String, default="source")
    voice_id: Mapped[str | None] = mapped_column(String)
    voice_name: Mapped[str | None] = mapped_column(String)
    voice_text_chapters: Mapped[dict | None] = mapped_column(JSONB)

    audio_url: Mapped[str | None] = mapped_column(Text)
    audio_chapter_urls: Mapped[dict | None] = mapped_column(JSONB)
    supabase_uploaded: Mapped[bool] = mapped_column(Boolean, default=False)
    is_uploaded: Mapped[bool] = mapped_column(Boolean, default=False)

    average_rating: Mapped[float | None] = mapped_column(Float)
    rating_count: Mapped[int] = mapped_column(Integer, default=0)
    review_count: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    voice_text_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    audio_generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    linear_id: Mapped[str] = mapped_column(String, nullable=False)
    language: Mapped[str] = mapped_column(String, nullable=False, default="english")
    rating: Mapped[float | None] = mapped_column(Float)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    reviewer_id: Mapped[str | None] = mapped_column(String)
    feedback_details: Mapped[dict | None] = mapped_column(JSONB)
    assignment_status: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PipelineJob(Base):
    __tablename__ = "pipeline_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    linear_id: Mapped[str] = mapped_column(String, nullable=False)
    language: Mapped[str] = mapped_column(String, nullable=False)
    job_type: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default="pending")
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

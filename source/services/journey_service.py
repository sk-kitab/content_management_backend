from __future__ import annotations
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from source.models import Journey, JourneyBook, Summary
from source.services.llm_clients import summary_response_gemini
from source.services.journey_prompts import journey_prompt1, Guide


class JourneyServiceError(Exception):
    pass


async def build_narration_prompt(
    journey_title: str,
    transformation: str,
    books: list[dict[str, Any]],
) -> str:
    """Build Gemini user prompt from journey data and book summaries."""
    if not books:
        raise JourneyServiceError("No books found for journey")

    book_parts = []
    for book in books:
        summary = book.get("final_summary", "").strip()
        title = book.get("summary_title") or book.get("search_title") or "Unknown"
        if summary:
            book_parts.append(f"--- Book: {title} ---\n{summary}\n")

    if not book_parts:
        raise JourneyServiceError("No book summaries found")

    return (
        f"JOURNEY_TOPIC: {journey_title}\n\n"
        f"BOOK_SUMMARIES:\n{''.join(book_parts)}"
        f"TARGET_TRANSFORMATION: {transformation}\n"
    )


async def get_books_with_summaries(
    journey_id: int,
    session: AsyncSession,
) -> list[dict[str, Any]]:
    """Fetch journey_books joined with summaries.final_summary."""
    result = await session.execute(
        select(JourneyBook, Summary.final_summary, Summary.title)
        .join(Summary, JourneyBook.summary_id == Summary.id)
        .where(JourneyBook.journey_id == journey_id)
        .order_by(JourneyBook.book_order)
    )
    rows = result.all()
    return [
        {
            "summary_title": jb.summary_title or summary_title,
            "search_title": jb.search_title,
            "final_summary": final_summary,
        }
        for jb, final_summary, summary_title in rows
    ]


async def generate_narration(journey_id: int, session: AsyncSession) -> str:
    """
    Run two-stage Gemini generation for a journey.
    Saves narration_text and narration_generated_at on success.
    Returns the generated narration text.
    """
    result = await session.execute(select(Journey).where(Journey.id == journey_id))
    journey = result.scalar_one_or_none()
    if not journey:
        raise JourneyServiceError(f"Journey {journey_id} not found")

    books = await get_books_with_summaries(journey_id, session)
    user_prompt = await build_narration_prompt(
        journey.journey_title,
        journey.transformation or "",
        books,
    )

    sections_text = summary_response_gemini(journey_prompt1, user_prompt)
    if not sections_text:
        raise JourneyServiceError("Gemini returned empty response for sections")

    narration_text = summary_response_gemini(Guide, f"JOURNEY_FRAMEWORK:\n{sections_text}")
    if not narration_text:
        raise JourneyServiceError("Gemini returned empty response for narration")

    journey.narration_text = narration_text
    journey.narration_generated_at = datetime.now(timezone.utc)
    await session.commit()

    return narration_text

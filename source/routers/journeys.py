from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from source.database import get_session
from source.models import Journey, JourneyBook
from source.schemas import (
    JourneyCard, JourneyDetail, JourneyCreate, JourneyPatch,
    JourneyBookRef, JourneyKanbanBoard, JourneyKanbanColumn,
)
from source.services.journey_service import generate_narration, JourneyServiceError, get_books_with_summaries

router = APIRouter(prefix="/api/journeys", tags=["journeys"])


async def _get_journey_or_404(linear_id: str, session: AsyncSession) -> Journey:
    result = await session.execute(
        select(Journey).where(Journey.linear_id == linear_id)
    )
    journey = result.scalar_one_or_none()
    if not journey:
        raise HTTPException(status_code=404, detail=f"Journey {linear_id} not found")
    return journey


async def _load_books(journey_id: int, session: AsyncSession) -> list[JourneyBookRef]:
    result = await session.execute(
        select(JourneyBook)
        .where(JourneyBook.journey_id == journey_id)
        .order_by(JourneyBook.book_order)
    )
    return [JourneyBookRef.model_validate(jb) for jb in result.scalars().all()]


@router.get("/kanban", response_model=JourneyKanbanBoard)
async def get_kanban(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(Journey))
    rows = result.scalars().all()

    columns: dict[str, list[JourneyCard]] = {
        "source": [], "creation": [], "push_to_linear": []
    }
    for row in rows:
        col = row.status if row.status in columns else "source"
        columns[col].append(JourneyCard.model_validate(row))

    return JourneyKanbanBoard(
        source=JourneyKanbanColumn(status="source", count=len(columns["source"]), items=columns["source"]),
        creation=JourneyKanbanColumn(status="creation", count=len(columns["creation"]), items=columns["creation"]),
        push_to_linear=JourneyKanbanColumn(status="push_to_linear", count=len(columns["push_to_linear"]), items=columns["push_to_linear"]),
    )


@router.get("/{linear_id}", response_model=JourneyDetail)
async def get_journey(linear_id: str, session: AsyncSession = Depends(get_session)):
    journey = await _get_journey_or_404(linear_id, session)
    books = await _load_books(journey.id, session)
    detail = JourneyDetail.model_validate(journey)
    detail.books = books
    return detail


@router.post("", response_model=JourneyDetail, status_code=201)
async def create_journey(body: JourneyCreate, session: AsyncSession = Depends(get_session)):
    journey = Journey(
        linear_id=body.linear_id,
        linear_issue_id=body.linear_issue_id,
        linear_assignee=body.linear_assignee,
        journey_title=body.journey_title,
        type=body.type,
        transformation=body.transformation,
        categories=body.categories,
        theme=body.theme,
        heartfulness_text=body.heartfulness_text,
        source_csv=body.source_csv,
        row_number=body.row_number,
        status=body.status,
        output_sections=body.output_sections,
    )
    session.add(journey)
    await session.flush()

    for order, summary_id in enumerate(body.book_summary_ids):
        session.add(JourneyBook(journey_id=journey.id, summary_id=summary_id, book_order=order))

    await session.commit()
    await session.refresh(journey)

    books = await _load_books(journey.id, session)
    detail = JourneyDetail.model_validate(journey)
    detail.books = books
    return detail


@router.patch("/{linear_id}", response_model=JourneyDetail)
async def patch_journey(
    linear_id: str,
    body: JourneyPatch,
    session: AsyncSession = Depends(get_session),
):
    journey = await _get_journey_or_404(linear_id, session)
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(journey, field, value)
    journey.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(journey)

    books = await _load_books(journey.id, session)
    detail = JourneyDetail.model_validate(journey)
    detail.books = books
    return detail


@router.post("/{linear_id}/generate-narration", response_model=JourneyDetail)
async def trigger_generate_narration(
    linear_id: str,
    session: AsyncSession = Depends(get_session),
):
    journey = await _get_journey_or_404(linear_id, session)
    try:
        await generate_narration(journey.id, session)
    except JourneyServiceError as e:
        raise HTTPException(status_code=422, detail=str(e))
    await session.refresh(journey)
    books = await _load_books(journey.id, session)
    detail = JourneyDetail.model_validate(journey)
    detail.books = books
    return detail


@router.delete("/{linear_id}", status_code=204)
async def delete_journey(linear_id: str, session: AsyncSession = Depends(get_session)):
    journey = await _get_journey_or_404(linear_id, session)
    await session.delete(journey)
    await session.commit()

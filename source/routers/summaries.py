# backend/routers/summaries.py
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from source.database import get_session
from source.models import Summary
from source.schemas import (
    SummaryCard, SummaryDetail, SummaryPatch,
    KanbanBoard, KanbanColumn,
)

router = APIRouter(prefix="/api/summaries", tags=["summaries"])

def _apply_filters(q, language: str, category: str | None, voice_name: str | None,
                   top_150: bool, search: str | None):
    q = q.where(Summary.language == language)
    if category:
        q = q.where(Summary.category == category)
    if voice_name:
        q = q.where(Summary.voice_name == voice_name)
    if top_150:
        q = q.where(Summary.top_150.is_(True))
    if search:
        like = f"%{search}%"
        q = q.where(or_(Summary.title.ilike(like), Summary.linear_id.ilike(like)))
    return q

@router.get("/kanban", response_model=KanbanBoard)
async def get_kanban(
    language: str = "english",
    category: str | None = None,
    voice_name: str | None = None,
    top_150: bool = False,
    search: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    q = _apply_filters(select(Summary), language, category, voice_name, top_150, search)
    result = await session.execute(q)
    rows = result.scalars().all()

    columns: dict[str, list[SummaryCard]] = {"source": [], "voice_text": [], "voice": []}
    for row in rows:
        col = row.voice_status if row.voice_status in columns else "source"
        columns[col].append(SummaryCard.model_validate(row))

    return KanbanBoard(
        source=KanbanColumn(status="source", count=len(columns["source"]), items=columns["source"]),
        voice_text=KanbanColumn(status="voice_text", count=len(columns["voice_text"]), items=columns["voice_text"]),
        voice=KanbanColumn(status="voice", count=len(columns["voice"]), items=columns["voice"]),
    )

@router.get("/categories", response_model=list[str])
async def list_categories(session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(Summary.category).where(Summary.category != None).distinct()
    )
    return sorted([r[0] for r in result.fetchall() if r[0]])

@router.get("/voices", response_model=list[str])
async def list_voices(
    language: str = "english",
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Summary.voice_name)
        .where(Summary.language == language, Summary.voice_name != None)
        .distinct()
    )
    return sorted([r[0] for r in result.fetchall() if r[0]])

@router.get("/{linear_id}", response_model=SummaryDetail)
async def get_summary(
    linear_id: str,
    language: str = "english",
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Summary).where(
            Summary.linear_id == linear_id,
            Summary.language == language,
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(404, f"Summary {linear_id} ({language}) not found")
    return SummaryDetail.model_validate(row)

@router.patch("/{linear_id}", response_model=SummaryDetail)
async def patch_summary(
    linear_id: str,
    body: SummaryPatch,
    language: str = "english",
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Summary).where(
            Summary.linear_id == linear_id,
            Summary.language == language,
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(404, f"Summary {linear_id} ({language}) not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(row, field, value)
    await session.commit()
    await session.refresh(row)
    return SummaryDetail.model_validate(row)

# backend/routers/reviews.py
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database import get_session
from backend.models import Review
from backend.schemas import ReviewOut

router = APIRouter(prefix="/api/reviews", tags=["reviews"])

@router.get("/{linear_id}", response_model=list[ReviewOut])
async def get_reviews(
    linear_id: str,
    language: str = "english",
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Review).where(
            Review.linear_id == linear_id,
            Review.language == language,
        ).order_by(Review.created_at.desc())
    )
    return [ReviewOut.model_validate(r) for r in result.scalars().all()]

from fastapi import APIRouter, HTTPException
from source.schemas import SupabaseReviewOut, ReviewStats
from source.services.supabase_client import review_client

router = APIRouter(prefix="/api/reviews", tags=["reviews"])


@router.get("/stats", response_model=ReviewStats)
async def get_review_stats():
    """Last month's review summary: approved vs requested-changes counts."""
    return await review_client.get_last_month_stats()


@router.get("/{linear_id}", response_model=list[SupabaseReviewOut])
async def get_reviews(linear_id: str):
    """
    All reviews for a summary from the Supabase review DB.
    Joins: summaries (linear_identifier) → content_assignments → reviews.
    Returns rating + assignment status per review.
    """
    reviews = await review_client.get_reviews_for_linear_id(linear_id)
    if not reviews:
        raise HTTPException(404, f"No reviews found for {linear_id}")
    return reviews

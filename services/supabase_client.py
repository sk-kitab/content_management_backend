import httpx
from backend.config import settings


class SupabaseReviewClient:
    def __init__(self) -> None:
        self.base_url = settings.review_supabase_url.rstrip("/")
        self._headers = {
            "apikey": settings.review_supabase_key,
            "Authorization": f"Bearer {settings.review_supabase_key}",
        }

    async def _get(self, table: str, params: dict) -> list[dict]:
        url = f"{self.base_url}/rest/v1/{table}"
        async with httpx.AsyncClient() as client:
            r = await client.get(url, headers=self._headers, params=params)
            r.raise_for_status()
            return r.json()

    async def get_reviews_for_linear_id(self, linear_id: str) -> list[dict]:
        summaries = await self._get("summaries", {
            "linear_identifier": f"eq.{linear_id}",
            "select": "id",
        })
        if not summaries:
            return []

        summary_uuid = summaries[0]["id"]

        # Fetch assignments with embedded reviews in one call (FK: reviews.assignment_id → content_assignments.id)
        assignments = await self._get("content_assignments", {
            "content_id": f"eq.{summary_uuid}",
            "content_type": "eq.summaries",
            "select": "id,status,iteration_count,assigned_at,completed_at,reviews(id,reviewer_id,rating,is_verified,created_at,feedback_details)",
        })
        if not assignments:
            return []

        results: list[dict] = []
        for assignment in assignments:
            for review in assignment.get("reviews") or []:
                results.append({
                    **review,
                    "assignment_id": assignment["id"],
                    "assignment_status": assignment["status"],
                    "iteration_count": assignment["iteration_count"],
                })

        results.sort(key=lambda r: r["created_at"], reverse=True)
        return results

    async def get_last_month_stats(self) -> dict:
        from datetime import datetime, timezone
        import calendar

        now = datetime.now(timezone.utc)
        year = now.year if now.month > 1 else now.year - 1
        month = now.month - 1 if now.month > 1 else 12
        last_day = calendar.monthrange(year, month)[1]

        start = datetime(year, month, 1, tzinfo=timezone.utc).isoformat()
        end = datetime(year, month, last_day, 23, 59, 59, tzinfo=timezone.utc).isoformat()

        # Reviews joined to content_assignments where content_type = summaries only
        reviews = await self._get("reviews", {
            "created_at": f"gte.{start}",
            "select": "id,rating,is_verified,created_at,content_assignments!inner(status,iteration_count,content_type)",
            "content_assignments.content_type": "eq.summaries",
        })
        # PostgREST applies AND when same param appears twice only via &, so filter second condition separately
        reviews = [r for r in reviews if r["created_at"] <= end]

        approved = sum(1 for r in reviews if (r.get("content_assignments") or {}).get("status") == "completed")
        requested_changes = sum(1 for r in reviews if (r.get("content_assignments") or {}).get("status") == "changes_requested")
        ratings = [r["rating"] for r in reviews if r.get("rating") is not None]

        return {
            "month": f"{year:04d}-{month:02d}",
            "total_reviewed": len(reviews),
            "approved": approved,
            "requested_changes": requested_changes,
            "average_rating": round(sum(ratings) / len(ratings), 2) if ratings else None,
        }


review_client = SupabaseReviewClient()

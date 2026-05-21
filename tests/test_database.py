import pytest
from sqlalchemy import text
from backend.database import SessionLocal
from backend.models import Summary, Review, PipelineJob

@pytest.mark.asyncio
async def test_db_connects():
    async with SessionLocal() as session:
        result = await session.execute(text("SELECT 1"))
        assert result.scalar() == 1

def test_summary_tablename():
    assert Summary.__tablename__ == "summaries"

def test_review_tablename():
    assert Review.__tablename__ == "reviews"

def test_pipeline_job_tablename():
    assert PipelineJob.__tablename__ == "pipeline_jobs"

import pytest
from httpx import AsyncClient, ASGITransport
from backend.main import app

@pytest.mark.asyncio
async def test_trigger_voice_text_enqueues_job():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/pipeline/trigger", json={
            "linear_id": "SUM-103",
            "language": "english",
            "job_type": "voice_text"
        })
    assert r.status_code == 202
    data = r.json()
    assert data["status"] == "pending"
    assert data["job_type"] == "voice_text"
    assert data["linear_id"] == "SUM-103"

@pytest.mark.asyncio
async def test_get_job_returns_job():
    # First create a job
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/pipeline/trigger", json={
            "linear_id": "SUM-103",
            "language": "english",
            "job_type": "voice_text"
        })
    job_id = r.json()["id"]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get(f"/api/pipeline/jobs/{job_id}")
    assert r.status_code == 200
    assert r.json()["id"] == job_id

@pytest.mark.asyncio
async def test_get_job_missing_returns_404():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/pipeline/jobs/999999")
    assert r.status_code == 404

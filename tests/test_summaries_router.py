import pytest
from httpx import AsyncClient, ASGITransport
from backend.main import app

@pytest.mark.asyncio
async def test_health():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}

@pytest.mark.asyncio
async def test_get_kanban_returns_three_columns():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/summaries/kanban?language=english")
    assert r.status_code == 200
    data = r.json()
    assert "source" in data
    assert "voice_text" in data
    assert "voice" in data
    assert isinstance(data["source"]["items"], list)

@pytest.mark.asyncio
async def test_categories_returns_list():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/summaries/categories")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
    assert len(r.json()) > 0

@pytest.mark.asyncio
async def test_get_summary_known_id():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/summaries/SUM-103?language=english")
    assert r.status_code == 200
    data = r.json()
    assert data["linear_id"] == "SUM-103"
    assert "title" in data

@pytest.mark.asyncio
async def test_get_summary_missing_returns_404():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/summaries/DOES-NOT-EXIST?language=english")
    assert r.status_code == 404

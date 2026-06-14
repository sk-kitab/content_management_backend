import pytest
from source.models import Journey, JourneyBook
from source.schemas import JourneyCard, JourneyDetail, JourneyCreate, JourneyPatch

def test_journey_model_has_expected_columns():
    cols = {c.key for c in Journey.__table__.columns}
    assert "journey_title" in cols
    assert "status" in cols
    assert "narration_text" in cols
    assert "output_sections" in cols

def test_journey_book_model_has_fk():
    fks = {fk.target_fullname for fk in JourneyBook.__table__.foreign_keys}
    assert any("journeys.id" in fk for fk in fks)
    assert any("summaries.id" in fk for fk in fks)

def test_journey_card_fields():
    card = JourneyCard(
        id=1,
        linear_id="JOU-69",
        journey_title="Agency Reboot",
        status="source",
    )
    assert card.journey_title == "Agency Reboot"

def test_journey_patch_partial():
    patch = JourneyPatch(status="creation")
    assert patch.status == "creation"
    assert patch.narration_text is None

def test_llm_clients_importable():
    from source.services.llm_clients import summary_response_gemini, summary_response_openai
    assert callable(summary_response_gemini)
    assert callable(summary_response_openai)

def test_journey_prompts_importable():
    from source.services.journey_prompts import journey_prompt1, Guide
    assert isinstance(journey_prompt1, str)
    assert isinstance(Guide, str)

from source.services.journey_service import build_narration_prompt, JourneyServiceError

def test_build_narration_prompt_raises_on_empty_books():
    with pytest.raises(JourneyServiceError, match="No books"):
        build_narration_prompt("Test Journey", "fear → calm", [])

def test_build_narration_prompt_returns_string():
    books = [{"summary_title": "Book A", "final_summary": "Summary text here"}]
    result = build_narration_prompt("Test Journey", "fear → calm", books)
    assert "Test Journey" in result
    assert "Summary text here" in result

from httpx import AsyncClient, ASGITransport
from backend.main import app

@pytest.mark.asyncio
async def test_journey_kanban_returns_three_columns():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/journeys/kanban")
    assert r.status_code == 200
    data = r.json()
    assert "source" in data
    assert "creation" in data
    assert "push_to_linear" in data
    assert isinstance(data["source"]["items"], list)

@pytest.mark.asyncio
async def test_journey_get_missing_returns_404():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/journeys/JOU-DOES-NOT-EXIST")
    assert r.status_code == 404

@pytest.mark.asyncio
async def test_journey_create_and_get():
    payload = {
        "journey_title": "Test Journey",
        "linear_id": "JOU-TEST-1",
        "status": "source",
        "book_summary_ids": [],
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r_create = await client.post("/api/journeys", json=payload)
        assert r_create.status_code == 201
        created_id = r_create.json()["linear_id"]
        try:
            r_get = await client.get(f"/api/journeys/{created_id}")
            assert r_get.status_code == 200
            assert r_get.json()["journey_title"] == "Test Journey"
        finally:
            await client.delete(f"/api/journeys/{created_id}")

@pytest.mark.asyncio
async def test_patch_journey_status():
    payload = {
        "journey_title": "Status Patch Test",
        "linear_id": "JOU-TEST-PATCH",
        "status": "source",
        "book_summary_ids": [],
    }
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r_create = await client.post("/api/journeys", json=payload)
        assert r_create.status_code == 201
        try:
            r_patch = await client.patch("/api/journeys/JOU-TEST-PATCH", json={"status": "creation"})
            assert r_patch.status_code == 200
            assert r_patch.json()["status"] == "creation"
        finally:
            await client.delete("/api/journeys/JOU-TEST-PATCH")

@pytest.mark.asyncio
async def test_generate_narration_missing_journey():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/journeys/JOU-GHOST/generate-narration")
    assert r.status_code == 404

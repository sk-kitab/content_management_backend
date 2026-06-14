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

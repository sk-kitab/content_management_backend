import pytest
from backend.source.models import Journey, JourneyBook

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

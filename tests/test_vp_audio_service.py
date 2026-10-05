from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from source.routers.summaries import kanban_column
from source.schemas import JobCreate
from source.services import audio_service
from source.services.audio_service import AudioResult, apply_audio_result, resolve_engine
from voice_pipeline.run import RunResult

NOW = datetime(2026, 10, 5, tzinfo=timezone.utc)


def test_resolve_engine_precedence():
    assert resolve_engine(None, None) == "legacy"
    assert resolve_engine(None, "v3") == "v3"
    assert resolve_engine("legacy", "v3") == "legacy"
    with pytest.raises(ValueError):
        resolve_engine("v9", None)


def test_job_create_engine_and_steps():
    job = JobCreate(linear_id="SUM-1", language="english", job_type="audio", engine="v3", steps={"qc_fix": False})
    assert job.engine == "v3" and job.steps == {"qc_fix": False}
    assert JobCreate(linear_id="SUM-1", language="english", job_type="audio").engine is None
    with pytest.raises(ValidationError):
        JobCreate(linear_id="SUM-1", language="english", job_type="audio", engine="v9")


def test_apply_result_pass_and_review():
    s = SimpleNamespace(audio_qc_report=None)
    apply_audio_result(s, AudioResult("u1", {"verdict": "pass"}, False), NOW)
    assert (s.voice_status, s.audio_url, s.audio_generated_at, s.supabase_uploaded) == ("voice", "u1", NOW, True)
    assert s.audio_qc_report == {"verdict": "pass"}
    apply_audio_result(s, AudioResult("u2", {"verdict": "needs_review"}, True), NOW)
    assert s.voice_status == "voice_review"


def test_legacy_result_keeps_existing_report():
    s = SimpleNamespace(audio_qc_report={"old": True})
    apply_audio_result(s, AudioResult("u"), NOW)
    assert s.audio_qc_report == {"old": True}


def test_v3_engine_runs_pipeline_and_uploads(monkeypatch, tmp_path):
    mp3 = tmp_path / "x.mp3"
    mp3.write_bytes(b"id3")
    seen = {}

    def fake_run(linear_id, language, title, final_summary, voice_id, steps):
        seen.update(linear_id=linear_id, title=title, steps=steps)
        return RunResult(mp3, {"verdict": "needs_review"})

    monkeypatch.setattr("voice_pipeline.run.run", fake_run)
    monkeypatch.setattr(audio_service, "replace_audio_in_supabase", lambda path, lid, lang: f"https://cdn/{lid}")
    result = audio_service.generate_audio("SUM-1", "english", "v1", "v3", "Title", "md", {"qc_fix": False})
    assert result == AudioResult("https://cdn/SUM-1", {"verdict": "needs_review"}, True)
    assert seen == {"linear_id": "SUM-1", "title": "Title", "steps": {"qc_fix": False}}


def test_kanban_column():
    assert kanban_column("voice_review") == "voice"
    assert kanban_column("voice_text") == "voice_text"
    assert kanban_column("weird") == "source"
    assert kanban_column(None) == "source"

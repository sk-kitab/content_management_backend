import pytest

from tests.vp_fakes import FakeQCRemote, FakeTTSClient, PermanentAPIError
from voice_pipeline import run as run_module
from voice_pipeline.normalization.llm_normalizer import LLMNormalizer
from voice_pipeline.profiles import PROFILES

MD = """### Introduction

The quiet mind notices more than the busy one ever could, and that is where we begin today.

### Key Idea 1 of 2: Slow down

When you slow down, 3 small details of the day come back into view and start to matter again.

### Key Idea 2 of 2: Look closer

Looking closer at ordinary things turns them into a source of calm attention and fresh ideas.
"""


class RaisingLLM(LLMNormalizer):
    def normalize_batch(self, items, language_hint="en"):
        raise RuntimeError("quota exceeded")


def go(tmp_path, client=None, remote=None, **kw):
    kw.setdefault("voice_id", "v1")
    return run_module.run("SUM-1", kw.pop("language", "English"), "Quiet Minds — A. Author", kw.pop("md", MD),
                          kw.pop("voice_id"), kw.pop("steps", None), work_root=tmp_path,
                          client=client or FakeTTSClient(), qc_remote=remote or FakeQCRemote(),
                          cache_path=tmp_path / "cache.json", **kw)


def test_end_to_end_pass(tmp_path):
    result = go(tmp_path)
    assert result.mp3_path.exists()
    assert result.report["verdict"] == "pass"
    assert not result.needs_review
    assert result.report["engine"] == "v3"
    assert set(result.report["acx"]) == {"rms_db", "peak_db", "noise_floor_db", "pass"}
    assert result.report["steps"]["qc_fix"] is True
    assert (tmp_path / "SUM-1" / "en" / "audio_qc_report.json").exists()


def test_still_failing_marks_needs_review_with_timestamps(tmp_path):
    result = go(tmp_path, remote=FakeQCRemote(drop_words={"*": 3}, drop_times=99))
    assert result.report["verdict"] == "needs_review"
    assert result.needs_review
    fails = [i for i in result.report["listen_list"] if i["verdict"] == "fail"]
    assert fails and all(isinstance(i["start_sec"], float) for i in fails)


def test_permanent_tts_error_fails_the_run(tmp_path):
    with pytest.raises(PermanentAPIError):
        go(tmp_path, client=FakeTTSClient(fail_with=PermanentAPIError()))


def test_language_casing_is_accepted(tmp_path):
    assert run_module.lang_code("HINDI") == "hi"
    assert run_module.lang_code(" english ") == "en"


def test_language_unsupported_fails_before_tts(tmp_path):
    client = FakeTTSClient()
    with pytest.raises(ValueError, match="tamil"):
        go(tmp_path, client=client, language="tamil")
    assert client.calls == []


def test_empty_summary_fails_before_tts(tmp_path):
    client = FakeTTSClient()
    with pytest.raises(ValueError, match="empty"):
        go(tmp_path, client=client, md="  \n\n ")
    assert client.calls == []


def test_missing_voice_uses_profile_default(tmp_path):
    client = FakeTTSClient()
    go(tmp_path, client=client, voice_id=None)
    assert {c["voice_id"] for c in client.calls} == {PROFILES["en"].default_voice_id}


def test_normalization_failure_is_noted_and_run_continues(tmp_path):
    result = go(tmp_path, steps={"normalize": True}, normalizer_llm=RaisingLLM())
    assert result.mp3_path.exists()
    assert any("quota exceeded" in n for n in result.report["notes"])


def test_missing_resemblyzer_is_noted(tmp_path, monkeypatch):
    monkeypatch.setattr(run_module, "speaker_similarity_available", lambda: False)
    result = go(tmp_path)
    assert "speaker similarity skipped: resemblyzer not installed" in result.report["notes"]

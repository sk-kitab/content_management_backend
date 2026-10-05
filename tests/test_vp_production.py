from pathlib import Path

import pytest

from tests.vp_fakes import TEXTS, FakeQCRemote, FakeTTSClient, make_chunks
from voice_pipeline.production import produce
from voice_pipeline.tts_client import VoicePreset

PRESET = VoicePreset(voice_id="v1", language_code="en")


def test_failing_chunk_is_regenerated_once_and_fixed(tmp_path):
    chunks = make_chunks(TEXTS)
    client = FakeTTSClient()
    remote = FakeQCRemote(drop_words={chunks[1].id: 3}, drop_times=1)
    summary = produce(tmp_path, chunks, PRESET, client, remote, overlap=False, qc_fix=True)
    assert summary["retries"][0]["fail"] == [chunks[1].id]
    assert summary["still_failing"] == []
    assert len(client.calls) == 4
    assert client.calls[-1]["seed"] == PRESET.seed + 1000
    assert Path(summary["output"]).exists()


def test_persistent_failure_stops_after_max_retries(tmp_path):
    chunks = make_chunks(TEXTS)
    client = FakeTTSClient()
    remote = FakeQCRemote(drop_words={chunks[1].id: 3}, drop_times=99)
    summary = produce(tmp_path, chunks, PRESET, client, remote, overlap=False, qc_fix=True, max_retries=2)
    assert summary["still_failing"] == [chunks[1].id]
    assert len(client.calls) == 5
    assert summary["counts"]["fail"] == 1
    assert any(i["chunk"] == chunks[1].id and i["verdict"] == "fail" for i in summary["listen_list"])


def test_assess_only_never_regenerates(tmp_path):
    chunks = make_chunks(TEXTS)
    client = FakeTTSClient()
    summary = produce(tmp_path, chunks, PRESET, client, FakeQCRemote(drop_words={"*": 3}, drop_times=99),
                      overlap=False, qc_fix=False)
    assert len(client.calls) == 3
    assert summary["retries"] == []
    assert len(summary["still_failing"]) == 3


def test_qc_off_needs_no_remote(tmp_path):
    summary = produce(tmp_path, make_chunks(TEXTS), PRESET, FakeTTSClient(), None,
                      overlap=False, qc_assess=False, qc_fix=False)
    assert summary["counts"] == {"pass": 0, "warn": 0, "fail": 0}
    assert len(summary["assembly_chunks"]) == 3


def test_assess_without_remote_is_an_error(tmp_path):
    with pytest.raises(ValueError):
        produce(tmp_path, make_chunks(TEXTS), PRESET, FakeTTSClient(), None, qc_assess=True)

import json

import pytest
import soundfile as sf

from tests.vp_fakes import GAP_SEC, SEC_PER_CHAR, TEXTS, FakeTTSClient, make_chunks
from voice_pipeline.generator import Generator
from voice_pipeline.overlap import lead_in_for, look_ahead_for
from voice_pipeline.tts_client import VoicePreset


def preset(**kw):
    return VoicePreset(voice_id="v1", language_code="en", **kw)


def test_preset_validation_and_fingerprint():
    with pytest.raises(ValueError):
        preset(stability="wild")
    with pytest.raises(ValueError):
        preset(use_pvc_as_ivc=True)
    assert preset().sample_rate == 44100
    assert preset().fingerprint() != preset(seed=1).fingerprint()


def test_lead_in_and_look_ahead_text():
    assert lead_in_for("First one. Second one.") == "Second one.\n\n"
    assert look_ahead_for("Next starts here. Then more.", "en") == "\n\nNext starts here."
    assert look_ahead_for(None, "hi") == "\n\nऔर यहीं हम थोड़ा रुकते हैं।"


def test_unchanged_chunks_are_skipped(tmp_path):
    client = FakeTTSClient()
    gen = Generator(client, preset(), tmp_path)
    chunks = make_chunks(TEXTS[:2])
    gen.generate(chunks)
    assert len(client.calls) == 2
    arts = Generator(client, preset(), tmp_path).generate(chunks)  # fresh instance reads manifest
    assert len(client.calls) == 2
    assert all(a.skipped for a in arts)


def test_editing_one_chunk_regenerates_only_it(tmp_path):
    client = FakeTTSClient()
    gen = Generator(client, preset(), tmp_path)
    chunks = make_chunks(TEXTS[:2])
    gen.generate(chunks)
    chunks[1].text = chunks[1].text + " Added."
    gen.generate(chunks)
    assert len(client.calls) == 3
    assert client.calls[-1]["text"].endswith("Added.")


def test_forced_regeneration_archives_previous_take(tmp_path):
    client = FakeTTSClient()
    gen = Generator(client, preset(), tmp_path)
    chunks = make_chunks(TEXTS[:1])
    gen.generate(chunks)
    gen.generate(chunks, force_ids={chunks[0].id}, seed=99)
    assert client.calls[-1]["seed"] == 99
    assert list((tmp_path / "chunks" / "versions").glob(f"{chunks[0].id}.*.wav"))


def test_overlap_cut_removes_lead_in_and_look_ahead(tmp_path):
    client = FakeTTSClient()
    gen = Generator(client, preset(), tmp_path)
    chunk = make_chunks(TEXTS[:1])[0]
    gen.generate([chunk], lead_ins={chunk.id: "Previous sentence here.\n\n"},
                 look_aheads={chunk.id: "\n\nNext sentence follows."})
    info = sf.info(str(tmp_path / "chunks" / f"{chunk.id}.wav"))
    expected = len(chunk.text) * SEC_PER_CHAR + GAP_SEC  # chunk tone + half a gap on each side
    assert abs(info.duration - expected) < 0.05
    meta = json.loads((tmp_path / "chunks" / f"{chunk.id}.alignment.json").read_text())
    assert meta["cut_start_sec"] is not None and meta["cut_end_sec"] is not None
    assert len(client.calls) == 1

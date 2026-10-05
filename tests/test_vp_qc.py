import json

from tests.vp_fakes import TEXTS, FakeQCRemote, make_chunks, write_chunk
from voice_pipeline.qc import acoustics
from voice_pipeline.qc.gate import run_qc
from voice_pipeline.qc.text_compare import compare


def test_exact_transcript_has_no_errors():
    c = compare("The cat sat on the mat.", "the cat sat on the mat", "en")
    assert c.wer == 0 and c.diffs == []


def test_skipped_and_repeated_words_are_counted():
    skipped = compare("one two three four five six", "one five six", "en")
    assert skipped.max_run_deleted == 3
    repeated = compare("one two three", "one two two two three", "en")
    assert repeated.max_run_inserted == 2


def test_digits_in_transcript_are_not_errors():
    c = compare("thirty percent of people agree", "30% of people agree", "en")
    assert c.wer == 0
    assert c.numeric_review == ["30"]


def test_hindi_spelling_variants_are_equivalent():
    assert compare("यह अच्छा है", "ये अच्छा है", "hi").wer == 0


def test_syllable_count():
    assert acoustics.count_syllables("banana", "en") == 3


def _setup(tmp_path):
    chunks = make_chunks(TEXTS)
    for c in chunks:
        write_chunk(tmp_path, c)
    return chunks


def test_clean_chunks_do_not_fail(tmp_path):
    chunks = _setup(tmp_path)
    results = run_qc(tmp_path, chunks, "en", FakeQCRemote())
    assert [r.verdict for r in results if r.verdict == "fail"] == []
    report = json.loads((tmp_path / "qc_report.json").read_text())
    assert len(report["chunks"]) == 3


def test_skipped_words_fail_the_chunk(tmp_path):
    chunks = _setup(tmp_path)
    results = run_qc(tmp_path, chunks, "en", FakeQCRemote(drop_words={chunks[1].id: 3}))
    assert results[1].verdict == "fail"
    assert any("consecutive script words not heard" in r for r in results[1].reasons)
    assert results[0].verdict != "fail"


def test_qc_outage_warns_and_continues(tmp_path):
    chunks = _setup(tmp_path)
    results = run_qc(tmp_path, chunks, "en", FakeQCRemote(fail_for={chunks[0].id}))
    assert results[0].verdict == "warn"
    assert any("qc_unavailable" in r for r in results[0].reasons)
    assert "wer" in results[1].metrics


def test_similarity_skipped_without_resemblyzer(tmp_path, monkeypatch):
    monkeypatch.setattr(acoustics, "speaker_similarity_available", lambda: False)
    chunks = _setup(tmp_path)
    results = run_qc(tmp_path, chunks, "en", FakeQCRemote())
    assert all("speaker_sim_anchor" not in r.metrics for r in results)

import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from tests.vp_fakes import TEXTS, make_chunks, silence, tone, write_chunk
from voice_pipeline import joiner

SR = 44100
needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


def test_trim_keeps_speech_and_short_tail():
    y = np.concatenate([silence(0.5), tone(1.0), silence(1.0)])
    out, lead, tail = joiner.trim(y, SR)
    assert abs(len(out) / SR - (1.0 + 0.03 + 0.30)) < 0.05
    assert lead > 0.4 and tail > 0.6


def test_long_inner_pause_is_capped():
    y = np.concatenate([tone(1.0), silence(3.0), tone(1.0)])
    out, n = joiner.cap_inner_pauses(y, SR)
    assert n == 1
    assert abs(len(out) / SR - 3.0) < 0.05


@needs_ffmpeg
def test_assemble_masters_mp3_and_offsets(tmp_path):
    chunks = make_chunks(TEXTS)
    chunks[0].boundary_after = "section"
    for c in chunks:
        write_chunk(tmp_path, c)
    report = joiner.assemble(tmp_path, chunks, {})
    assert Path(report["outputs"]["mastered_mp3"]).exists()
    assert set(report["final"]) >= {"rms_db", "peak_db", "noise_floor_db", "acx_ok"}
    offsets = joiner.chunk_offsets(report, chunks)
    starts = [offsets[c.id] for c in chunks]
    assert starts[0] == joiner.PAUSES_SEC["head"]
    gap = starts[1] - starts[0] - report["chunks"][0]["duration_sec"]
    assert abs(gap - joiner.PAUSES_SEC["section"]) < 2e-3
    assert starts[2] > starts[1]


@needs_ffmpeg
def test_require_ffmpeg_filters_passes_here():
    joiner.require_ffmpeg_filters()


def test_require_ffmpeg_filters_names_missing_filter(monkeypatch):
    monkeypatch.setattr(joiner.shutil, "which", lambda name: "/usr/bin/ffmpeg")
    fake = subprocess.CompletedProcess([], 0, stdout=" ... loudnorm  A->A  x\n T.. deesser  A->A  x\n", stderr="")
    monkeypatch.setattr(joiner.subprocess, "run", lambda *a, **k: fake)
    with pytest.raises(RuntimeError, match="rubberband"):
        joiner.require_ffmpeg_filters()

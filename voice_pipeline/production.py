"""
Production loop for one title + language (adapted from reference production.py):

    generate (idempotent) -> QC -> regenerate failures & pace outliers with a new seed (max N)
    -> re-QC -> assemble + master -> summary (what still needs a human listen)

Glue over generator, qc, joiner — no audio or QC logic lives here. The TTS client and QC remote
are passed in so tests run without network.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np

from voice_pipeline.generator import Generator
from voice_pipeline.joiner import assemble
from voice_pipeline.overlap import lead_in_for, look_ahead_for
from voice_pipeline.qc.gate import run_qc
from voice_pipeline.tts_client import VoicePreset

log = logging.getLogger(__name__)

PACE_REGEN_THRESHOLD = 0.15   # syllables/sec deviation beyond which one regeneration is tried


def _paces(results) -> dict[str, float]:
    return {q.chunk_id: q.metrics["syllables_per_sec"] for q in results if q.metrics.get("syllables_per_sec")}


def _pace_outliers(results) -> set[str]:
    rates = _paces(results)
    if len(rates) < 4:  # too few chunks for a stable median
        return set()
    med = float(np.median(list(rates.values())))
    return {cid for cid, r in rates.items() if abs(med / r - 1) > PACE_REGEN_THRESHOLD}


def build_lead_ins(chunks: list) -> dict[str, str]:
    """Overlap-and-trim lead-ins: previous chunk's last sentence, only within a section."""
    out = {}
    for prev, cur in zip(chunks, chunks[1:]):
        if prev.section == cur.section:
            lead = lead_in_for(prev.text)
            if lead:
                out[cur.id] = lead
    return out


def build_look_aheads(chunks: list) -> dict[str, str]:
    """Next chunk's first sentence (any section) so every chunk's last word can decay naturally."""
    out = {}
    for i, c in enumerate(chunks):
        nxt = chunks[i + 1].text if i < len(chunks) - 1 else None
        out[c.id] = look_ahead_for(nxt, c.lang)
    return out


def produce(run_dir: Path, chunks: list, preset: VoicePreset, client, qc_remote,
            max_retries: int = 2, anchor_wav: Path | None = None, overlap: bool = True,
            pause_extension: bool = False, qc_assess: bool = True, qc_fix: bool = False) -> dict:
    if qc_fix:
        qc_assess = True
    if qc_assess and qc_remote is None:
        raise ValueError("qc_assess needs a QC remote")
    gen = Generator(client, preset, run_dir)
    lang = chunks[0].lang
    lead_ins = build_lead_ins(chunks) if overlap else {}
    look_aheads = build_look_aheads(chunks) if overlap else {}

    log.info(f"[1/3] generating {len(chunks)} chunks ({len(lead_ins)} with lead-in, {len(look_aheads)} with look-ahead)")
    gen.generate(chunks, lead_ins=lead_ins, look_aheads=look_aheads)

    history, results = [], []
    if qc_assess:
        results = run_qc(run_dir, chunks, lang, qc_remote, anchor_wav)
    if qc_fix:
        pace_tried: set[str] = set()
        for attempt in range(1, max_retries + 1):
            failing = {q.chunk_id for q in results if q.verdict == "fail"}
            pace = {cid for cid in _pace_outliers(results) if cid not in pace_tried}
            pace_tried |= pace  # one pace retry only; if still off, pace is text-driven -> joiner stretches it
            todo = failing | pace
            if not todo:
                break
            log.info(f"      retry {attempt}/{max_retries}: {sorted(todo)} (fail={sorted(failing)}, pace={sorted(pace)})")
            history.append({"attempt": attempt, "fail": sorted(failing), "pace": sorted(pace)})
            gen.generate([c for c in chunks if c.id in todo], force_ids=todo, seed=preset.seed + 1000 * attempt,
                         lead_ins=lead_ins, look_aheads=look_aheads)
            results = run_qc(run_dir, chunks, lang, qc_remote, anchor_wav)

    log.info("[2/3] assembling + mastering")
    metrics = {q.chunk_id: q.metrics for q in results}  # empty when qc off -> pace matching disabled
    report = assemble(run_dir, chunks, metrics, pause_extension=pause_extension)

    summary = {
        "qc_assess": qc_assess, "qc_fix": qc_fix,
        "retries": history,
        "counts": {v: sum(q.verdict == v for q in results) for v in ("pass", "warn", "fail")},
        "still_failing": [q.chunk_id for q in results if q.verdict == "fail"],
        "listen_list": [{"chunk": q.chunk_id, "verdict": q.verdict, "reasons": q.reasons}
                        for q in results if q.verdict != "pass"],
        "pace_regen_suggested_after_retries": [e["chunk_id"] for e in report["chunks"] if e["regenerate_suggested"]],
        "assembly_chunks": report["chunks"],
        "final": report["final"],
        "output": report["outputs"]["mastered_mp3"],
    }
    (run_dir / "production_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False, default=float))
    log.info(f"[3/3] done -> {summary['output']}")
    return summary

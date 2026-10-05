"""
v3 engine entry point: one summary + language -> mastered mp3 + QC report.

Glue only: text prep (loader -> normalize -> pronunciation -> chunk), production (generate ->
QC -> fix -> assemble), and the report the CMS stores in summaries.audio_qc_report. Everything
that can fail without spending credits (language, ffmpeg, empty text) is checked first.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from voice_pipeline.chunking import Chunk, chunk_title
from voice_pipeline.joiner import chunk_offsets, require_ffmpeg_filters
from voice_pipeline.loader import load_sections
from voice_pipeline.normalization.cache_store import JSONFileCache
from voice_pipeline.normalization.llm_normalizer import GeminiNormalizer
from voice_pipeline.normalization.pipeline import NormalizationPipeline, normalize_safely
from voice_pipeline.production import produce
from voice_pipeline.profiles import PROFILES, anchor_for, resolve_steps
from voice_pipeline.pronunciation import Pronunciation
from voice_pipeline.qc.acoustics import speaker_similarity_available
from voice_pipeline.qc.elevenlabs_checks import ElevenLabsQC
from voice_pipeline.tts_client import ElevenLabsClient, VoicePreset

log = logging.getLogger(__name__)

LANG_CODES = {"english": "en", "en": "en", "hindi": "hi", "hi": "hi"}
CACHE_PATH = Path(__file__).resolve().parent / "data" / "normalization_cache.json"
MAX_RETRIES = 2


@dataclass
class RunResult:
    mp3_path: Path
    report: dict

    @property
    def needs_review(self) -> bool:
        return self.report["verdict"] == "needs_review"


def lang_code(language: str) -> str:
    code = LANG_CODES.get((language or "").strip().lower())
    if code is None:
        raise ValueError(f"v3 voice pipeline supports English and Hindi, got language={language!r}")
    return code


def _normalizer(lang: str, steps: dict, notes: list[str], llm, cache_path: Path):
    if not steps["normalize"]:
        return None
    if llm is None:
        from source.config import settings
        if not settings.google_genai_api_key:
            notes.append("normalization skipped: google_genai_api_key not set")
            return None
        llm = GeminiNormalizer(settings.google_genai_api_key)
    return NormalizationPipeline(JSONFileCache(cache_path), llm, language_hint=lang)


def prepare_chunks(final_summary: str, title: str, lang: str, normalizer, pronunciation,
                   notes: list[str]) -> list[Chunk]:
    sections = load_sections(final_summary, title)
    if not sections:
        raise ValueError("final_summary is empty — nothing to narrate")

    def prep(text: str) -> str:
        if text and normalizer is not None:
            text = normalize_safely(normalizer, text, notes)
        if text and pronunciation is not None:
            text = pronunciation.apply(text)
        return text

    return chunk_title([(s.slug, prep(s.heading), [prep(p) for p in s.paragraphs]) for s in sections], lang)


def build_report(summary: dict, offsets: dict[str, float], steps: dict, notes: list[str]) -> dict:
    final = summary["final"]
    return {
        "engine": "v3",
        "verdict": "needs_review" if summary["still_failing"] else "pass",
        "counts": summary["counts"],
        "listen_list": [{"chunk_id": i["chunk"], "verdict": i["verdict"],
                         "start_sec": offsets.get(i["chunk"]), "reasons": i["reasons"]}
                        for i in summary["listen_list"]],
        "retries": summary["retries"],
        "acx": {"rms_db": final["rms_db"], "peak_db": final["peak_db"],
                "noise_floor_db": final["noise_floor_db"], "pass": bool(final["acx_ok"])},
        "notes": notes,
        "steps": steps,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def run(linear_id: str, language: str, title: str, final_summary: str, voice_id: str | None,
        steps: dict | None = None, *, work_root: Path | None = None, client=None, qc_remote=None,
        normalizer_llm=None, cache_path: Path = CACHE_PATH) -> RunResult:
    lang = lang_code(language)
    st = resolve_steps(lang, steps)
    notes: list[str] = []
    require_ffmpeg_filters()

    pronunciation = Pronunciation.load(lang) if st["pronunciation"] else None
    normalizer = _normalizer(lang, st, notes, normalizer_llm, cache_path)
    chunks = prepare_chunks(final_summary, title, lang, normalizer, pronunciation, notes)

    from source.config import settings
    voice = voice_id or PROFILES[lang].default_voice_id
    preset = VoicePreset(voice_id=voice, language_code=lang, stability=PROFILES[lang].stability,
                         pronunciation_dictionary_locators=pronunciation.locators if pronunciation else ())
    run_dir = Path(work_root or Path(settings.audios_root) / "v3_work") / linear_id / lang
    run_dir.mkdir(parents=True, exist_ok=True)

    if client is None:
        client = ElevenLabsClient(settings.elevenlabs_api_key)
    if qc_remote is None and st["qc_assess"]:
        qc_remote = ElevenLabsQC(settings.elevenlabs_api_key, run_dir / "qc_cache")
    if not st["qc_assess"]:
        notes.append("QC assessment off — audio not checked")
    elif not speaker_similarity_available():
        notes.append("speaker similarity skipped: resemblyzer not installed")

    log.info(f"v3 run {linear_id}/{lang}: {len(chunks)} chunks, voice {voice}, steps {st}")
    summary = produce(run_dir, chunks, preset, client, qc_remote, max_retries=MAX_RETRIES,
                      anchor_wav=anchor_for(voice), overlap=st["overlap"],
                      pause_extension=st["pause_extension"], qc_assess=st["qc_assess"], qc_fix=st["qc_fix"])

    offsets = chunk_offsets({"chunks": summary["assembly_chunks"]}, chunks)
    report = build_report(summary, offsets, st, notes)
    (run_dir / "audio_qc_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False, default=float))
    return RunResult(Path(summary["output"]), report)

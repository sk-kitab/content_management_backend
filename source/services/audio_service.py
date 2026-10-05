# backend/services/audio_service.py
from dataclasses import dataclass
from datetime import datetime

from source.config import settings

from modules.chapter_audio_processor import process_chapters_to_final_audio
from modules.supabase_utils import replace_audio_in_supabase

ENGINES = ("legacy", "v3")


@dataclass
class AudioResult:
    url: str
    qc_report: dict | None = None
    needs_review: bool = False


def resolve_engine(job_engine: str | None, summary_engine: str | None) -> str:
    """Job override, then the summary's column, then legacy."""
    engine = job_engine or summary_engine or "legacy"
    if engine not in ENGINES:
        raise ValueError(f"unknown audio engine {engine!r}; expected one of {ENGINES}")
    return engine


def generate_audio(linear_id: str, language: str, voice_id: str | None, engine: str = "legacy",
                   title: str = "", final_summary: str = "", steps: dict | None = None) -> AudioResult | None:
    if engine == "v3":
        return _generate_v3(linear_id, language, voice_id, title, final_summary, steps)
    url = _generate_legacy(linear_id, language, voice_id)
    return AudioResult(url) if url else None


def apply_audio_result(summary, result: AudioResult, now: datetime) -> None:
    summary.voice_status = "voice_review" if result.needs_review else "voice"
    summary.audio_url = result.url
    summary.audio_generated_at = now
    summary.supabase_uploaded = True
    summary.audio_qc_report = result.qc_report  # None for legacy: clears a stale v3 report


def _generate_v3(linear_id: str, language: str, voice_id: str | None, title: str,
                 final_summary: str, steps: dict | None) -> AudioResult:
    from voice_pipeline.run import run  # heavy audio deps load only when v3 is used
    result = run(linear_id, language, title, final_summary, voice_id, steps)
    url = replace_audio_in_supabase(str(result.mp3_path), linear_id, language)
    return AudioResult(url, result.report, result.needs_review)


def _generate_legacy(linear_id: str, language: str, voice_id: str | None) -> str | None:
    lang = language.lower()
    if lang == "english":
        voice_texts_dir = settings.voice_texts_dir
        pre_audio_dir = f"{settings.audios_root}/english_pre_audio"
        audios_dir = f"{settings.audios_root}/english-final"
    else:
        voice_texts_dir = "hindi_texts"
        pre_audio_dir = f"{settings.audios_root}/hindi_pre_audio"
        audios_dir = f"{settings.audios_root}/hindi-final"

    result = process_chapters_to_final_audio(
        json_id=linear_id,
        voice_texts_dir=voice_texts_dir,
        pre_audio_dir=pre_audio_dir,
        audios_dir=audios_dir,
        voice_id=voice_id or "",
        use_llm=(lang == "english"),
        language=language.capitalize(),
    )
    if not result:
        return None

    return replace_audio_in_supabase(str(result), linear_id, language)

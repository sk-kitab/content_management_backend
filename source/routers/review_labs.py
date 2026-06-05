import asyncio
import json
import os
import subprocess
from typing import Literal

import httpx
from deepgram import DeepgramClient
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from source.database import get_session
from source.models import Summary

router = APIRouter(prefix="/api/review-labs", tags=["review-labs"])

_BASE = os.path.join(os.path.dirname(__file__), "..", "..", "tmp")
TRANSCRIPT_DIR = os.getenv("REVIEW_LABS_TRANSCRIPT_DIR", os.path.join(_BASE, "transcripts"))
AUDIO_DIR = os.getenv("REVIEW_LABS_AUDIO_DIR", os.path.join(_BASE, "audio"))
EXPORT_DIR = os.getenv("REVIEW_LABS_EXPORT_DIR", os.path.join(_BASE, "exports"))


class WordDetail(BaseModel):
    word: str
    start: float
    end: float
    confidence: float
    speaker: int | None = None


class TranscriptResponse(BaseModel):
    linear_id: str
    words: list[WordDetail]
    duration: float


def _infer_ext(url: str) -> str:
    ext = os.path.splitext(url.split("?")[0])[1]
    return ext if ext else ".mp3"


async def _download_audio(url: str, dest: str) -> str:
    async with httpx.AsyncClient() as client:
        r = await client.get(url, follow_redirects=True)
        r.raise_for_status()
    with open(dest, "wb") as f:
        f.write(r.content)
    return dest


@router.get("/{linear_id}/transcript", response_model=TranscriptResponse)
async def get_transcript(
    linear_id: str,
    language: str = "english",
    session: AsyncSession = Depends(get_session),
):
    os.makedirs(TRANSCRIPT_DIR, exist_ok=True)
    cache_path = os.path.join(TRANSCRIPT_DIR, f"{linear_id}-{language}.json")
    if os.path.exists(cache_path):
        with open(cache_path) as f:
            return TranscriptResponse(**json.load(f))

    result = await session.execute(
        select(Summary).where(
            Summary.linear_id == linear_id,
            Summary.language == language,
        )
    )
    summary = result.scalar_one_or_none()
    if not summary:
        raise HTTPException(404, f"Summary {linear_id} not found")
    if not summary.audio_url:
        raise HTTPException(400, "Summary has no audio URL")

    os.makedirs(AUDIO_DIR, exist_ok=True)
    ext = _infer_ext(summary.audio_url)
    audio_path = os.path.join(AUDIO_DIR, f"{linear_id}{ext}")
    if not os.path.exists(audio_path):
        try:
            await _download_audio(summary.audio_url, audio_path)
        except Exception as e:
            raise HTTPException(500, f"Failed to download audio: {e}")

    api_key = os.getenv("deepgram_apikey")
    if not api_key:
        raise HTTPException(500, "Deepgram API key not configured")

    def _transcribe():
        dg = DeepgramClient(api_key=api_key)
        with open(audio_path, "rb") as f:
            buf = f.read()
        return dg.listen.v1.media.transcribe_file(
            request=buf,
            model="nova-3",
            smart_format=True,
            utterances=True,
            punctuate=True,
            diarize=True,
        )

    try:
        response = await asyncio.get_running_loop().run_in_executor(None, _transcribe)
    except Exception as e:
        raise HTTPException(500, f"Transcription failed: {e}")

    words = []
    duration = 0.0
    if response and response.results and response.results.channels:
        channel = response.results.channels[0]
        if not channel.alternatives:
            pass  # skip word extraction
        else:
            alt = channel.alternatives[0]
            words_list = getattr(alt, "words", []) or []
            for w in words_list:
                w_dict = w if isinstance(w, dict) else (w.model_dump() if hasattr(w, "model_dump") else {})
                words.append({
                    "word": getattr(w, "word", w_dict.get("word", "")),
                    "start": getattr(w, "start", w_dict.get("start", 0.0)),
                    "end": getattr(w, "end", w_dict.get("end", 0.0)),
                    "confidence": getattr(w, "confidence", w_dict.get("confidence", 0.0)),
                    "speaker": getattr(w, "speaker", w_dict.get("speaker", None)),
                })
        if response.metadata:
            meta = response.metadata
            meta_dict = meta if isinstance(meta, dict) else (meta.model_dump() if hasattr(meta, "model_dump") else {})
            duration = getattr(meta, "duration", meta_dict.get("duration", 0.0))

    payload = {"linear_id": linear_id, "words": words, "duration": duration}
    with open(cache_path, "w") as f:
        json.dump(payload, f)

    return TranscriptResponse(**payload)


class EditRange(BaseModel):
    type: Literal["delete", "mute"]
    start: float
    end: float

    @model_validator(mode="after")
    def start_before_end(self):
        if self.start >= self.end:
            raise ValueError("start must be less than end")
        return self


class ExportRequest(BaseModel):
    edits: list[EditRange]
    format: Literal["mp3", "wav", "ogg"] = "mp3"


_MEDIA_TYPES = {"mp3": "audio/mpeg", "wav": "audio/wav", "ogg": "audio/ogg"}


def _get_keep_segments(duration: float, deletions: list[EditRange]) -> list[dict]:
    segments: list[dict] = []
    cursor = 0.0
    for d in sorted(deletions, key=lambda x: x.start):
        if cursor < d.start:
            segments.append({"start": cursor, "end": d.start})
        cursor = d.end
    if cursor < duration:
        segments.append({"start": cursor, "end": duration})
    return segments


@router.post("/{linear_id}/export")
async def export_audio(
    linear_id: str,
    body: ExportRequest,
    language: str = "english",
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Summary).where(
            Summary.linear_id == linear_id,
            Summary.language == language,
        )
    )
    summary = result.scalar_one_or_none()
    if not summary:
        raise HTTPException(404, f"Summary {linear_id} not found")
    if not summary.audio_url:
        raise HTTPException(400, "Summary has no audio URL")

    os.makedirs(AUDIO_DIR, exist_ok=True)
    ext = _infer_ext(summary.audio_url)
    audio_path = os.path.join(AUDIO_DIR, f"{linear_id}{ext}")
    if not os.path.exists(audio_path):
        try:
            await _download_audio(summary.audio_url, audio_path)
        except Exception as e:
            raise HTTPException(500, f"Failed to download audio: {e}")

    def _run_ffprobe():
        return subprocess.check_output([
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            audio_path,
        ])

    try:
        duration = float(
            (await asyncio.get_running_loop().run_in_executor(None, _run_ffprobe)).decode().strip()
        )
    except Exception as e:
        raise HTTPException(500, f"ffprobe failed: {e}")

    deletions = [e for e in body.edits if e.type == "delete"]
    mutes = [e for e in body.edits if e.type == "mute"]
    keep_segments = _get_keep_segments(duration, deletions)

    if not keep_segments:
        raise HTTPException(400, "All audio deleted — nothing to export")

    filters: list[str] = []
    labels: list[str] = []
    base_stream = "[0:a]"

    if mutes:
        enable_expr = "+".join(f"between(t,{m.start},{m.end})" for m in mutes)
        filters.append(f"[0:a]volume=0:enable='{enable_expr}'[muted]")
        base_stream = "[muted]"

    if len(keep_segments) > 1:
        split_labels = "".join(f"[base{i}]" for i in range(len(keep_segments)))
        filters.append(f"{base_stream}asplit={len(keep_segments)}{split_labels}")
        for i, s in enumerate(keep_segments):
            filters.append(f"[base{i}]atrim={s['start']}:{s['end']},asetpts=PTS-STARTPTS[a{i}]")
            labels.append(f"[a{i}]")
    else:
        for i, s in enumerate(keep_segments):
            filters.append(f"{base_stream}atrim={s['start']}:{s['end']},asetpts=PTS-STARTPTS[a{i}]")
            labels.append(f"[a{i}]")

    filter_complex = ";".join(filters)
    if len(keep_segments) > 1:
        filter_complex += ";" + "".join(labels) + f"concat=n={len(keep_segments)}:v=0:a=1[out]"
        map_label = "[out]"
    else:
        map_label = "[a0]"

    os.makedirs(EXPORT_DIR, exist_ok=True)
    output_path = os.path.join(EXPORT_DIR, f"{linear_id}_edited.{body.format}")

    def _run_ffmpeg():
        subprocess.run(
            ["ffmpeg", "-y", "-i", audio_path, "-filter_complex", filter_complex, "-map", map_label, output_path],
            check=True,
            capture_output=True,
        )

    try:
        await asyncio.get_running_loop().run_in_executor(None, _run_ffmpeg)
    except subprocess.CalledProcessError as e:
        raise HTTPException(500, f"ffmpeg failed: {e.stderr.decode()}")

    with open(output_path, "rb") as f:
        content = f.read()

    return Response(
        content=content,
        media_type=_MEDIA_TYPES[body.format],
        headers={"Content-Disposition": f'attachment; filename="{linear_id}_edited.{body.format}"'},
    )

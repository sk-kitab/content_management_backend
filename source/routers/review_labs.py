import asyncio
import json
import os

import httpx
from deepgram import DeepgramClient
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
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
    cache_path = os.path.join(TRANSCRIPT_DIR, f"{linear_id}.json")
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
        await _download_audio(summary.audio_url, audio_path)

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
        alt = response.results.channels[0].alternatives[0]
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

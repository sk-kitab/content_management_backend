"""Test doubles for the v3 voice pipeline: deterministic audio, no network."""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import soundfile as sf

from voice_pipeline.chunking import Chunk
from voice_pipeline.tts_client import GenerationResult

SEC_PER_CHAR = 0.03
GAP_SEC = 0.4
LEAD_SEC = 0.1
TAIL_SEC = 0.3

TEXTS = [
    "The quiet mind notices more than the busy one ever could, and that is where we begin.",
    "When you slow down, small details of the day come back into view and start to matter.",
    "Looking closer at ordinary things turns them into a source of calm attention and ideas.",
]


def tone(seconds: float, sr: int = 44100, freq: float = 180.0, amp: float = 0.3) -> np.ndarray:
    t = np.arange(int(seconds * sr)) / sr
    return (amp * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def silence(seconds: float, sr: int = 44100) -> np.ndarray:
    return np.zeros(int(seconds * sr), dtype=np.float32)


class PermanentAPIError(Exception):
    status_code = 401


class FakeTTSClient:
    """Speaks each "\\n\\n"-separated paragraph as a tone (SEC_PER_CHAR s per character) with
    GAP_SEC of digital silence between paragraphs, and returns a matching character alignment —
    the same shape a lead-in / look-ahead gives a real generation."""

    def __init__(self, fail_with: Exception | None = None):
        self.calls: list[dict] = []
        self.fail_with = fail_with

    def generate(self, text, preset, seed=None) -> GenerationResult:
        self.calls.append({"text": text, "seed": seed, "voice_id": preset.voice_id})
        if self.fail_with is not None:
            raise self.fail_with
        sr = preset.sample_rate
        audio = [silence(LEAD_SEC, sr)]
        chars, starts, ends = [], [], []
        t = LEAD_SEC
        for seg in re.split(r"(\n\n)", text):
            if not seg:
                continue
            if seg == "\n\n":
                step = GAP_SEC / 2
                audio.append(silence(GAP_SEC, sr))
            else:
                step = SEC_PER_CHAR
                audio.append(tone(len(seg) * SEC_PER_CHAR, sr))
            for ch in seg:
                chars.append(ch)
                starts.append(round(t, 4))
                ends.append(round(t + step, 4))
                t += step
        audio.append(silence(TAIL_SEC, sr))
        pcm = (np.concatenate(audio) * 32767).astype(np.int16).tobytes()
        alignment = {"characters": chars, "character_start_times_seconds": starts,
                     "character_end_times_seconds": ends}
        return GenerationResult(pcm=pcm, alignment=alignment, normalized_alignment=None,
                                request_id="fake", character_cost=len(text), quality_check=None,
                                seed=preset.seed if seed is None else seed)


class FakeQCRemote:
    """QC remote double. transcribe() "hears" the chunk's script (read from the alignment file
    written next to each wav), minus its first N words for chunks in drop_words ("*" = every
    chunk) on the first drop_times calls for that chunk. align() times each word by its syllable
    count at a constant 4 syllables/s, so pace never looks like an outlier."""

    def __init__(self, drop_words: dict[str, int] | None = None, drop_times: int = 1,
                 fail_for: set[str] | None = None):
        self.drop_words = drop_words or {}
        self.drop_times = drop_times
        self.fail_for = fail_for or set()
        self.transcribe_calls: dict[str, int] = {}

    @staticmethod
    def _script(wav: Path) -> str:
        return json.loads((wav.parent / f"{wav.stem}.alignment.json").read_text())["text"]

    def transcribe(self, wav: Path, lang: str) -> dict:
        cid = wav.stem
        if cid in self.fail_for:
            raise ConnectionError("scribe unavailable")
        n = self.transcribe_calls.get(cid, 0) + 1
        self.transcribe_calls[cid] = n
        words = self._script(wav).split()
        drop = self.drop_words.get(cid, self.drop_words.get("*", 0))
        if drop and n <= self.drop_times:
            words = words[drop:]
        return {"text": " ".join(words), "language_code": lang, "words": []}

    def align(self, wav: Path, text: str) -> dict:
        from voice_pipeline.qc.acoustics import count_syllables
        out, t = [], 0.1
        for w in text.split():
            lang = "hi" if re.search(r"[ऀ-ॿ]", w) else "en"
            d = count_syllables(w, lang) / 4.0
            out.append({"text": w, "start": round(t, 4), "end": round(t + d, 4), "loss": 0.1})
            t += d
        return {"loss": 0.1, "words": out}


def make_chunks(texts: list[str], lang: str = "en", section: str = "key_idea_1") -> list[Chunk]:
    return [Chunk(f"{section}_{i + 1:02d}", lang, section, i, t,
                  "end" if i == len(texts) - 1 else "paragraph")
            for i, t in enumerate(texts)]


def write_chunk(run_dir: Path, chunk: Chunk, sr: int = 44100) -> Path:
    """A chunk wav + alignment file, as the generator would leave them."""
    y = np.concatenate([silence(LEAD_SEC, sr), tone(len(chunk.text) * SEC_PER_CHAR, sr), silence(TAIL_SEC, sr)])
    wav = run_dir / "chunks" / f"{chunk.id}.wav"
    wav.parent.mkdir(parents=True, exist_ok=True)
    sf.write(wav, y, sr, subtype="PCM_16")
    (wav.parent / f"{chunk.id}.alignment.json").write_text(json.dumps({"text": chunk.text}))
    return wav

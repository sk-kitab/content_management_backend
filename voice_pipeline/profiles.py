"""
Per-language defaults for the v3 engine (adapted from reference profiles.py). The voice comes from
the summary; a profile supplies the fallback voice, the stability preset, and which steps run.

Step resolution: profile defaults <- job `steps` overrides (later wins). `qc_fix` implies
`qc_assess`. Defaults: text transforms off, overlap + QC assess + QC fix on.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ANCHOR_DIR = Path(__file__).resolve().parent / "data" / "anchors"

# Approved reference clips per ElevenLabs voice id, for voice-similarity QC. A voice with no clip
# is compared against its own first generated chunk.
ANCHORS: dict[str, str] = {
    "ZXdqz9XCKNwPN16HnQWr": "hi_kitab_narrator_v2.wav",
}

STEP_KEYS = ("normalize", "pronunciation", "overlap", "qc_assess", "qc_fix", "pause_extension")


@dataclass(frozen=True)
class LanguageProfile:
    lang: str
    default_voice_id: str
    stability: str = "natural"      # natural | robust (never creative for long-form)
    normalize: bool = False         # numbers/dates/units -> spoken words (Gemini)
    pronunciation: bool = False     # data/pronunciation.json aliases
    overlap: bool = True            # lead-in + look-ahead, trimmed at real silence
    qc_assess: bool = True          # Scribe + alignment + acoustic checks -> report
    qc_fix: bool = True             # regenerate failing chunks (max 2)
    pause_extension: bool = False   # post-production minimum pauses


PROFILES = {
    "en": LanguageProfile(lang="en", default_voice_id="NaKPQmdr7mMxXuXrNeFC"),  # legacy DEFAULT_VOICE_ID
    "hi": LanguageProfile(lang="hi", default_voice_id="ZXdqz9XCKNwPN16HnQWr"),  # reference hi narrator
}


def resolve_steps(lang: str, *overrides: dict | None) -> dict[str, bool]:
    prof = PROFILES[lang]
    steps = {k: getattr(prof, k) for k in STEP_KEYS}
    for ov in overrides:
        for k, v in (ov or {}).items():
            if v is None or k not in steps:
                continue
            steps[k] = bool(v)
    if steps["qc_fix"]:
        steps["qc_assess"] = True  # fixing needs assessment to decide what to fix
    return steps


def anchor_for(voice_id: str) -> Path | None:
    name = ANCHORS.get(voice_id)
    path = ANCHOR_DIR / name if name else None
    return path if path is not None and path.exists() else None

"""
Pronunciation fixes applied to text before TTS, per language, from data/pronunciation.json:

  aliases   whole-word respellings (grapheme -> alias), e.g. "Satguru" -> "सतगुरु"
  locators  pre-uploaded ElevenLabs pronunciation dictionaries [[dictionary_id, version_id], ...]
            sent with every request

Shape: {"en": {"aliases": {...}, "locators": [...]}, "hi": {...}}. Edit the JSON by hand.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parent / "data" / "pronunciation.json"
_WORD = r"\w\u0900-\u097f"  # \w skips Devanagari vowel signs, so include the block explicitly


@dataclass
class Pronunciation:
    aliases: dict[str, str] = field(default_factory=dict)
    locators: tuple[tuple[str, str], ...] = ()

    @classmethod
    def load(cls, lang: str, path: Path = DEFAULT_PATH) -> "Pronunciation":
        if not path.exists():
            return cls()
        raw = json.loads(path.read_text(encoding="utf-8")).get(lang) or {}
        return cls(
            aliases=dict(raw.get("aliases") or {}),
            locators=tuple((str(i), str(v)) for i, v in raw.get("locators") or []),
        )

    def apply(self, text: str) -> str:
        if not self.aliases:
            return text
        keys = sorted(self.aliases, key=len, reverse=True)  # "Kamlesh D. Patel" before "D. Patel"
        pattern = re.compile(rf"(?<![{_WORD}])(?:{'|'.join(re.escape(k) for k in keys)})(?![{_WORD}])")
        return pattern.sub(lambda m: self.aliases[m.group()], text)

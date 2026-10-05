"""
final_summary markdown -> clean, speakable sections (adapted from reference content/kitab_loader.py).

Headings ("#".."######") start sections: "Key Idea N of M" / "मुख्य विचार M में से N" become
key ideas, the first section is the intro, the last is the summary, anything else is a numbered
section. Text before the first heading is kept as the intro. Slugs are unique within a title
because chunk ids and chunk files are named after them.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

_KEY_IDEA_EN = re.compile(r"key\s+idea\s+(\d+)\s+of\s+(\d+)", re.I)
_KEY_IDEA_HI = re.compile(r"मुख्य\s+विचार\s+(\d+)\s+में\s+से\s+(\d+)")
_SEPARATOR = re.compile(r"[-_=]{3,}")


@dataclass
class Section:
    kind: str           # "intro" | "key_idea" | "section" | "summary"
    index: int          # key idea number / position; 0 for intro, 99 for summary
    heading: str        # spoken form ("Key Idea 1 of 6. Use Vitamin G."); "" when none
    paragraphs: list[str] = field(default_factory=list)
    slug: str = ""      # unique within the title; set by load_sections


def clean_markdown(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)          # bold
    text = re.sub(r"(?<!\w)\*(.+?)\*(?!\w)", r"\1", text)  # italics
    text = text.replace("*", "").replace("#", "")
    text = re.sub(r"([?!])\1+", r"\1", text)              # "??" -> "?"
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def _classify(heading: str, position: int, total: int) -> tuple[str, int]:
    m = _KEY_IDEA_EN.search(heading)
    if m:
        return "key_idea", int(m.group(1))
    m = _KEY_IDEA_HI.search(heading)
    if m:
        # Hindi phrasing is "मुख्य विचार <total> में से <n>" — the index is the SECOND number
        return "key_idea", int(m.group(2))
    if position == 0:
        return "intro", 0
    if position == total - 1:
        return "summary", 99
    return "section", position


def _spoken_heading(heading: str) -> str:
    # "Key Idea 1 of 6: Use X" -> "Key Idea 1 of 6. Use X." — a colon reads poorly aloud; a full
    # stop gives the natural beat a narrator puts after a chapter number.
    h = clean_markdown(heading.lstrip("#").strip())
    stop = "।" if re.search(r"[ऀ-ॿ]", h) else "."
    h = re.sub(r"\s*:\s*", f"{stop} ", h, count=1)
    if h and h[-1] not in ".?!।":
        h += stop
    return h


def _spoken_title(title: str) -> str:
    # "Atomic Habits — James Clear (2018)" -> "Atomic Habits by James Clear."
    t = re.sub(r"\([^)]*\)", "", title or "")
    t = re.sub(r"\s+[—-]\s+", " by ", t, count=1)
    return _spoken_heading(t)


def _paragraphs(body: str) -> list[str]:
    out = []
    for raw in re.split(r"\n\s*\n", body):
        p = clean_markdown(raw)
        if p and not _SEPARATOR.fullmatch(p):
            out.append(p)
    return out


def _base_slug(kind: str, index: int) -> str:
    return {"intro": "intro", "summary": "summary"}.get(kind, f"{kind}_{index}")


def load_sections(final_summary: str, title: str = "") -> list[Section]:
    parts = re.split(r"(?m)^(#{1,6}.*)$", final_summary or "")
    preamble = _paragraphs(parts[0])
    headed = [(parts[i], _paragraphs(parts[i + 1])) for i in range(1, len(parts), 2)]
    headed = [(h, body) for h, body in headed if body]
    total = len(headed) + (1 if preamble else 0)

    sections: list[Section] = []
    if preamble:
        sections.append(Section("intro", 0, "", preamble))
    for heading, paragraphs in headed:
        kind, index = _classify(heading, len(sections), total)
        sections.append(Section(kind, index, _spoken_heading(heading), paragraphs))

    seen: dict[str, int] = {}
    for s in sections:
        base = _base_slug(s.kind, s.index)
        n = seen.get(base, 0)
        seen[base] = n + 1
        s.slug = base if n == 0 else f"{base}_{chr(ord('a') + n)}"

    if title and sections:
        sections[0].heading = _spoken_title(title)
    return sections

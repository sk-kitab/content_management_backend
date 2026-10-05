from voice_pipeline.chunking import MAX_CHARS, chunk_title
from voice_pipeline.loader import load_sections

EN_MD = """### Introduction

Hello world, this is the start.

### Key Idea 1 of 2: Be Kind

Para one.

Para two.

### Key Idea 2 of 2: Rest

Para three.

### Final Summary

The end.
"""


def test_english_key_ideas_become_sections():
    sections = load_sections(EN_MD)
    assert [s.slug for s in sections] == ["intro", "key_idea_1", "key_idea_2", "summary"]
    assert sections[1].heading == "Key Idea 1 of 2. Be Kind."
    assert sections[1].paragraphs == ["Para one.", "Para two."]


def test_title_replaces_first_heading():
    sections = load_sections(EN_MD, "Atomic Habits — James Clear")
    assert sections[0].heading == "Atomic Habits by James Clear."


def test_hindi_key_idea_index_is_second_number():
    md = "### परिचय\n\nनमस्ते।\n\n### मुख्य विचार 3 में से 1: धीरे चलें\n\nधीरे चलना अच्छा है।\n\n### सारांश\n\nअंत।"
    sections = load_sections(md)
    assert [s.slug for s in sections] == ["intro", "key_idea_1", "summary"]
    assert sections[1].heading.endswith("।")


def test_no_headings_become_one_intro_section():
    sections = load_sections("Just text.\n\nMore text.")
    assert len(sections) == 1
    assert sections[0].slug == "intro"
    assert sections[0].heading == ""
    assert sections[0].paragraphs == ["Just text.", "More text."]


def test_preamble_before_first_heading_is_kept():
    sections = load_sections("Pre text.\n\n## A\n\nx.\n\n## B\n\ny.\n\n## C\n\nz.")
    assert [s.slug for s in sections] == ["intro", "section_1", "section_2", "summary"]
    assert sections[0].paragraphs == ["Pre text."]


def test_duplicate_and_generic_headings_get_unique_slugs():
    md = "## Key Idea 1 of 2: A\n\nx.\n\n## Key Idea 1 of 2: B\n\ny.\n\n## Chapter\n\nz.\n\n## Chapter\n\nw."
    slugs = [s.slug for s in load_sections(md)]
    assert len(slugs) == len(set(slugs))
    assert slugs[:2] == ["key_idea_1", "key_idea_1_b"]


def test_markdown_and_separators_are_stripped():
    sections = load_sections("## A\n\n**Bold** words and *soft* ones.\n\n---\n\n***\n\nLast.")
    assert sections[0].paragraphs == ["Bold words and soft ones.", "Last."]


def test_empty_summary_has_no_sections():
    assert load_sections("") == []
    assert load_sections("   \n\n ") == []


def test_chunks_never_span_sections_and_carry_boundaries():
    sections = [("intro", "Intro.", ["a" * 100, "b" * 100]), ("key_idea_1", "Idea.", ["c" * 100])]
    chunks = chunk_title(sections, "en")
    assert [c.id for c in chunks] == ["intro_01", "key_idea_1_01"]
    assert [c.boundary_after for c in chunks] == ["section", "end"]
    assert chunks[0].text.startswith("Intro.\n")


def test_long_paragraph_splits_at_sentence_ends():
    para = " ".join(f"Sentence number {i} is right here." for i in range(80))  # ~2700 chars
    chunks = chunk_title([("intro", "", [para])], "en")
    assert len(chunks) >= 3
    assert all(c.chars <= MAX_CHARS for c in chunks)
    assert all(c.text.endswith(".") for c in chunks)


def test_unpunctuated_long_paragraph_is_hard_wrapped_without_losing_words():
    words = [f"word{i}" for i in range(600)]  # ~4400 chars, no sentence punctuation
    chunks = chunk_title([("intro", "", [" ".join(words)])], "en")
    assert all(c.chars <= MAX_CHARS for c in chunks)
    assert " ".join(c.text for c in chunks).split() == words


def test_merge_respects_separator_length():
    # Regression: merge conditions used +1 but join uses "\n\n" (2 chars), causing 951-char chunks
    # This test ensures that even when paragraphs fit with +1, merge doesn't happen if +2 would exceed
    para_a = "a" * 200 + "."  # 201 chars
    para_b = "b" * 747 + "."  # 748 chars
    # With separator: 201 + 2 + 748 = 951 chars (exceeds MAX_CHARS=950)
    chunks = chunk_title([("intro", "", [para_a, para_b])], "en")
    assert all(c.chars <= MAX_CHARS for c in chunks), f"Found chunk with {max(c.chars for c in chunks)} chars"
    assert len(chunks) == 2  # Should not merge


def test_merge_allows_exact_max_chars_with_separator():
    # Inverse: verify that paragraphs that fit exactly WITH the separator still merge
    para_a = "a" * 200 + "."  # 201 chars
    para_b = "b" * 747       # 747 chars (201 + 2 + 747 = 950, exactly MAX_CHARS)
    chunks = chunk_title([("intro", "", [para_a, para_b])], "en")
    assert all(c.chars <= MAX_CHARS for c in chunks)
    assert len(chunks) == 1  # Should merge into one chunk of exactly 950 chars

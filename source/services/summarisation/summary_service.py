import os
from google import genai
from google.genai import types

from source.config import settings

_KEY_IDEA_PROMPT = """
You are an expert nonfiction distiller. Your job is to extract the few core ideas that power the book's argument, not to summarize chapters. Prioritize accuracy, author intent, transferability, and clarity. Avoid speculation.

TASK: Read the provided book content and propose 8–15 candidate KEY IDEAS (claims), then compress to the strongest 3–8.

RULES
- A key idea is a generalizable claim the author wants readers to remember and use. It is NOT a chapter title or a one-off anecdote.
- Prefer ideas that:
  (a) repeat across chapters (Repetition Test),
  (b) are prerequisites for other points (Scaffold Test),
  (c) change behavior or perception (Transfer Test),
  (d) are supported by evidence/examples in the text (Evidence Test).
- Merge overlaps; remove sub-points that belong under a larger idea.

OUTPUT (CANDIDATES)
For each candidate (8–15):
- Claim (max 18 words, sentence-case)
- Why it matters (1 sentence)
- Best supporting evidence (brief; page/location if available)
- Is it foundational? (yes/no)
- Overlap with others? (list IDs)

Then SELECT the strongest 3–8 and justify inclusion in 1–2 sentences each.

TASK: Turn each chosen claim into a user-facing heading using one of these patterns:
- "Do X to get Y" (imperative, benefit-led)
- "Why X is harder/easier than you think" (myth-bust)
- "Before you X, do Y" (sequence/primer)
- "Instead of X, try Y" (contrast)
- "Remember: X beats Y" (rule of thumb)
- "Protect yourself: X while Y" (guardrail)

RULES
- Max 12 words per heading.
- No jargon; second-person or imperative voice.
- Headings must be self-explanatory (reader grasps the idea from the title alone).

OUTPUT
List the final 3–8 headings with a one-line "idea essence" under each.

TASK: For each heading, write 150–220 words covering:
1) The claim (what it says, in plain English).
2) Why it matters (so-what).
3) How it works / how to apply (one actionable move).
4) One concrete illustration (study, example, metaphor) from the book.
5) Minimal cite (page/location) if provided; else omit.

STYLE
- Second person where natural, present tense, short sentences.
- Concrete > abstract. Avoid "In this book," "Chapter X," or filler.
- No invented facts. If info is not in the input, don't add it.

## Final Output Format (per idea)
- **Title**: (Following content cue framework above, Only use it as a reference)
- **Source Integration**: Which original chapters contribute to this Key Idea
- **Justification**: Why this Key Idea was selected
"""

_BS_PROMPT = """
# Book Summary Creation Prompt

You are an Experienced writer who specializes in writing engaging book summaries with a listenable experience. Your goal is to craft a summary that feels like reading a mini version of the book.

**Summary Structure:**
- Total listening time should be between 16-22 minutes.( According to the book's length)
- Follow the key ideas as provided in context.
- Follow this exact structure: Introduction → Key Idea Chapters → Conclusion

**Key Idea Chapter Creation Process:**
1. Key Idea are our version of chapters of the book
2. You will be provided with already extracted key idea chapters with reference to original chapters
3. Use these key Ideas as heading of the chapters and references for summarise the original chapters.
4. For key idea name, it should always follow this format: Key Idea {number} of {total number of key ideas}: {Title}

## Detailed Structure Guidelines

**Introduction** (150-200 words)
Structure the introduction with these elements in sequence:
1. **###What You'll Take Away? Headline:** Open with a direct benefit promise as a question or answer.
2. **Hooking Story/Anecdote (ONLY if compelling story exists in book)**
3. **Problem Context:** Zoom out briefly to explain why this challenge matters.
4. **Preview Teaser (optional):** Hint at 2-3 surprising discoveries ahead.

**Key Idea Chapters** (300-500 words each)
- Start with hooking Anecdote/Metaphor/Example from the book
- Frame the rest as the solution using the chapter's principle and research
- Provide an actionable item directly from the book
- Build logical connection toward the next key idea chapter
- Transition smoothly to the next chapter

**Conclusion** (150-200 words)
- Open with a powerful restatement of the book's core thesis.
- Provide a small summary and key message from the book.
- Provide one key idea not covered in above chapters.
- In the end provide an actionable item to the user.

### Core Principle: Complete Rewriting Required
**Rule 1:** Capture only ideas and facts. Never reproduce the author's specific words.
**Rule 2:** Summaries must use entirely original wording.
**Rule 3:** Direct quotes are prohibited unless absolutely necessary.

## Writing Style
- Varied sentence length: short punchy statements mixed with flowing explanations.
- Direct second-person ("You'll discover...") or inclusive first-person plural.
- Strong, active verbs: "summon, carve, forge, anchor, compound, rewire"
- Immediate translation of technical terms.
- Warm, hopeful, evidence-driven yet inspirational tone.
- No bullet points in the summary. No mention that you are an AI.
"""


def _call_gemini(user_prompt: str, system_instruction: str) -> str:
    api_key = settings.google_genai_api_key or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_GENAI_API_KEY not set")
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model="gemini-2.5-pro",
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            max_output_tokens=8192,
            temperature=0.5,
        ),
    )
    return response.text


def generate_summary(book_text: str) -> tuple[str, str]:
    """
    Two-pass Gemini summary generation.

    Returns (initial_summary, final_summary):
    - initial_summary: key ideas extraction (pass 1)
    - final_summary: full narrative summary using key ideas (pass 2)
    """
    key_ideas = _call_gemini(
        f"Here is the Book\n{book_text}",
        _KEY_IDEA_PROMPT,
    )
    final = _call_gemini(
        f"Here is the Book to summarise\n{book_text}\n\nHere are the Key Ideas extracted from the book\n{key_ideas}",
        _BS_PROMPT,
    )
    return key_ideas, final

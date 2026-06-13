import os
import logging
from typing import Optional
from dataclasses import dataclass, field
from pydantic import BaseModel, Field
from google import genai
from google.genai import types

from source.config import settings

logger = logging.getLogger(__name__)

_SOP_POLICY = """1. The Core Principle (Idea vs. Expression): The reviewer must check that the summary only uses the ideas from the original work, not the author's specific expression (their words and sentences). The summary must re-write said ideas in your own words.

2. The Direct SOP Rule: Kitab should summarise the work in its own words and not use the words of the author of the work to convey its meaning.

3. The Rule on Quoting (De Minimis): If any direct quotes are used, they must adhere to the strict quoting policy: Kitab should not use more than a single sentence of 5-10 words from the original work."""

_COPYRIGHT_PROMPT = """You are a legal content analyst specializing in copyright law. Analyze the given book text and determine whether it is likely under copyright protection based on Indian copyright law and the Berne Convention rules.

From the provided text, extract:
- Title
- Author(s)
- Year of creation/publication
- Place of first publication

Apply the Copyright Term Test:
- If published within the last 60 years -> under copyright
- If published more than 60 years ago -> copyright expired (public domain)
- Ancient works (e.g., Bhagavad Gita, Upanishads) -> public domain

Determine the copyright status and provide detailed justification."""


class _CopyrightStatusSchema(BaseModel):
    status: str = Field(description="Either 'Under Copyright' or 'Public Domain'")
    title: str = Field(description="Title of the work")
    author: str = Field(description="Author of the work")
    publication_year: str = Field(description="Year of publication")
    justification: str = Field(description="Detailed justification for the copyright status")
    confidence: float = Field(description="Confidence score between 0.0 and 1.0")


class _SentenceRewriteSchema(BaseModel):
    summary_sentence: str = Field(description="The problematic sentence from the summary")
    reference_sentence: str = Field(description="The sentence from the book this summary sentence copies")
    suggested_rewrite: str = Field(description="Compliant rewrite of this specific sentence")
    reason: str = Field(description="Brief explanation of why this sentence needed rewriting")


class _LLMJudgeSchema(BaseModel):
    problematic_sentences: Optional[list[_SentenceRewriteSchema]] = Field(
        description="List of all problematic sentences with rewrites, null if compliant"
    )


@dataclass
class SentenceViolation:
    summary_sentence: str
    reference_sentence: str
    suggested_rewrite: str
    reason: str


@dataclass
class CopyrightResult:
    is_under_copyright: bool
    violations: list[SentenceViolation] = field(default_factory=list)
    copyright_status: str = ""
    title: str = ""
    author: str = ""
    publication_year: str = ""
    justification: str = ""
    confidence: float = 0.0


def _call_gemini_structured(user_prompt: str, system_prompt: str, schema: type, model: str = "gemini-2.5-flash"):
    api_key = settings.google_genai_api_key or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_GENAI_API_KEY or GOOGLE_API_KEY must be set")
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model,
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            max_output_tokens=65536,
            temperature=0.3,
            response_schema=schema,
            response_mime_type="application/json",
        ),
    )
    return schema.model_validate_json(response.text or "{}")


def check_copyright(book_text: str, summary_text: str) -> CopyrightResult:
    """
    Run full copyright compliance check.

    Returns CopyrightResult with:
    - is_under_copyright: True if book is under copyright
    - violations: list of sentences that need rewriting (empty if none/public domain)
    """
    book_start = book_text[:5000]
    book_end = book_text[-5000:] if len(book_text) > 5000 else ""
    copyright_user_prompt = (
        f"Book Text to Analyze:\n\nBEGINNING:\n{book_start}\n\nEND:\n{book_end}"
        if book_end
        else f"Book Text to Analyze:\n{book_start}"
    )

    status_result = _call_gemini_structured(
        user_prompt=copyright_user_prompt,
        system_prompt=_COPYRIGHT_PROMPT,
        schema=_CopyrightStatusSchema,
        model="gemini-2.5-flash",
    )
    logger.info("Copyright status: %s", status_result.status)

    violations: list[SentenceViolation] = []

    if status_result.status == "Under Copyright":
        judge_system = (
            "You are an expert copyright compliance judge. Evaluate whether the given summary "
            f"follows our SOP policy and identify ALL violations.\n\nSOP POLICY:\n{_SOP_POLICY}"
        )
        judge_user = (
            f"ORIGINAL BOOK TEXT:\n{book_text}\n\n"
            f"SUMMARY TO EVALUATE:\n{summary_text}\n\n"
            "Identify ALL sentences that violate the SOP policy. For each problematic sentence "
            "provide the exact sentence, the corresponding original book sentence, a compliant "
            "rewrite, and a brief reason. If no violations exist, return null for problematic_sentences."
        )

        judge_result = _call_gemini_structured(
            user_prompt=judge_user,
            system_prompt=judge_system,
            schema=_LLMJudgeSchema,
            model="gemini-2.5-pro",
        )

        if judge_result.problematic_sentences:
            violations = [
                SentenceViolation(
                    summary_sentence=s.summary_sentence,
                    reference_sentence=s.reference_sentence,
                    suggested_rewrite=s.suggested_rewrite,
                    reason=s.reason,
                )
                for s in judge_result.problematic_sentences
            ]

    return CopyrightResult(
        is_under_copyright=status_result.status == "Under Copyright",
        violations=violations,
        copyright_status=status_result.status,
        title=status_result.title,
        author=status_result.author,
        publication_year=status_result.publication_year,
        justification=status_result.justification,
        confidence=status_result.confidence,
    )


def apply_rewrites(summary: str, violations: list[SentenceViolation]) -> str:
    """Replace each flagged sentence with its suggested rewrite."""
    revised = summary
    for v in violations:
        revised = revised.replace(v.summary_sentence, v.suggested_rewrite, 1)
    return revised

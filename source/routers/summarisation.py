import asyncio
import os
from datetime import datetime, timezone

import fitz
import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from source.config import settings
from source.database import SessionLocal, get_session
from source.models import PipelineJob, Summary
from source.services.summarisation.copyright_service import (
    CopyrightResult,
    apply_rewrites,
    check_copyright,
)
from source.services.summarisation.summary_service import generate_summary

router = APIRouter(prefix="/api/summarisation", tags=["summarisation"])

_BASE = os.path.join(os.path.dirname(__file__), "..", "..", "tmp")
BOOKS_DIR = os.getenv("SUMMARISATION_BOOKS_DIR", os.path.join(_BASE, "books"))


# ── Schemas ──────────────────────────────────────────────────────────────────

class SummarisationStatus(BaseModel):
    linear_id: str
    summarisation_status: str | None
    job_id: int | None = None
    job_status: str | None = None
    error: str | None = None


class CopyrightReport(BaseModel):
    linear_id: str
    copyright_status: str | None
    violations: list[dict]


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _fetch_pdf(pdf_supabase_path: str, dest: str) -> None:
    url = (
        f"{settings.supabase_url}/storage/v1/object/"
        f"{settings.supabase_books_bucket}/{pdf_supabase_path}"
    )
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.get(
            url,
            headers={
                "apikey": settings.supabase_key,
                "Authorization": f"Bearer {settings.supabase_key}",
            },
            follow_redirects=True,
        )
        r.raise_for_status()
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as f:
            f.write(r.content)


def _extract_text(pdf_path: str) -> str:
    doc = fitz.open(pdf_path)
    pages = [doc.load_page(i).get_text() for i in range(len(doc))]
    doc.close()
    return "\n\n".join(p for p in pages if p.strip())


# ── Background tasks ──────────────────────────────────────────────────────────

async def _run_copyright_check(linear_id: str, language: str, book_text: str, final_summary: str) -> None:
    async with SessionLocal() as session:
        await session.execute(
            update(Summary)
            .where(Summary.linear_id == linear_id, Summary.language == language)
            .values(summarisation_status="copyright_checking")
        )
        await session.commit()

        try:
            result: CopyrightResult = await asyncio.get_running_loop().run_in_executor(
                None, check_copyright, book_text, final_summary
            )

            violations_json = [
                {
                    "summary_sentence": v.summary_sentence,
                    "reference_sentence": v.reference_sentence,
                    "suggested_rewrite": v.suggested_rewrite,
                    "reason": v.reason,
                }
                for v in result.violations
            ]

            revised = (
                await asyncio.get_running_loop().run_in_executor(
                    None, apply_rewrites, final_summary, result.violations
                )
                if result.violations
                else None
            )

            new_status = "copyright_failed" if result.violations else "copyright_passed"

            await session.execute(
                update(Summary)
                .where(Summary.linear_id == linear_id, Summary.language == language)
                .values(
                    summarisation_status=new_status,
                    copyright_report={
                        "copyright_status": result.copyright_status,
                        "title": result.title,
                        "author": result.author,
                        "publication_year": result.publication_year,
                        "justification": result.justification,
                        "confidence": result.confidence,
                        "violations": violations_json,
                    },
                    copyright_revised_summary=revised,
                )
            )
            await session.commit()

        except Exception:
            await session.rollback()
            await session.execute(
                update(Summary)
                .where(Summary.linear_id == linear_id, Summary.language == language)
                .values(summarisation_status="copyright_check_failed")
            )
            await session.commit()


async def _run_summarisation(job_id: int, linear_id: str, language: str) -> None:
    async with SessionLocal() as session:
        await session.execute(
            update(PipelineJob)
            .where(PipelineJob.id == job_id)
            .values(status="running", started_at=datetime.now(timezone.utc))
        )
        await session.execute(
            update(Summary)
            .where(Summary.linear_id == linear_id, Summary.language == language)
            .values(summarisation_status="summarising")
        )
        await session.commit()

        try:
            result = await session.execute(
                select(Summary).where(
                    Summary.linear_id == linear_id, Summary.language == language
                )
            )
            summary = result.scalar_one_or_none()
            if not summary:
                raise ValueError(f"Summary {linear_id}/{language} not found")
            if not summary.pdf_supabase_path:
                raise ValueError("pdf_supabase_path is not set — upload PDF to Supabase first")

            os.makedirs(BOOKS_DIR, exist_ok=True)
            pdf_dest = os.path.join(BOOKS_DIR, f"{linear_id}.pdf")
            if not os.path.exists(pdf_dest):
                await _fetch_pdf(summary.pdf_supabase_path, pdf_dest)

            book_text = await asyncio.get_running_loop().run_in_executor(
                None, _extract_text, pdf_dest
            )

            initial_summary, final_summary = await asyncio.get_running_loop().run_in_executor(
                None, generate_summary, book_text
            )

            await session.execute(
                update(Summary)
                .where(Summary.linear_id == linear_id, Summary.language == language)
                .values(
                    initial_summary=initial_summary,
                    final_summary=final_summary,
                    summarisation_status="summarised",
                )
            )
            await session.execute(
                update(PipelineJob)
                .where(PipelineJob.id == job_id)
                .values(status="done", completed_at=datetime.now(timezone.utc))
            )
            await session.commit()

            # Auto-trigger copyright check
            asyncio.create_task(
                _run_copyright_check(linear_id, language, book_text, final_summary)
            )

        except Exception as exc:
            await session.rollback()
            await session.execute(
                update(Summary)
                .where(Summary.linear_id == linear_id, Summary.language == language)
                .values(summarisation_status="summarisation_failed")
            )
            await session.execute(
                update(PipelineJob)
                .where(PipelineJob.id == job_id)
                .values(status="failed", error=str(exc), completed_at=datetime.now(timezone.utc))
            )
            await session.commit()


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/{linear_id}/start", status_code=202)
async def start_summarisation(
    linear_id: str,
    background_tasks: BackgroundTasks,
    language: str = "english",
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Summary).where(
            Summary.linear_id == linear_id, Summary.language == language
        )
    )
    summary = result.scalar_one_or_none()
    if not summary:
        raise HTTPException(404, f"Summary {linear_id} not found")
    if not summary.pdf_supabase_path:
        raise HTTPException(400, "pdf_supabase_path not set — upload PDF to Supabase first")
    if summary.summarisation_status in ("summarising", "copyright_checking"):
        raise HTTPException(409, "Summarisation already in progress")

    job = PipelineJob(
        linear_id=linear_id,
        language=language,
        job_type="summarise",
        status="pending",
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    background_tasks.add_task(_run_summarisation, job.id, linear_id, language)
    return {"job_id": job.id, "status": "pending"}


@router.get("/{linear_id}/status", response_model=SummarisationStatus)
async def get_status(
    linear_id: str,
    language: str = "english",
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Summary).where(
            Summary.linear_id == linear_id, Summary.language == language
        )
    )
    summary = result.scalar_one_or_none()
    if not summary:
        raise HTTPException(404, f"Summary {linear_id} not found")

    job_result = await session.execute(
        select(PipelineJob)
        .where(
            PipelineJob.linear_id == linear_id,
            PipelineJob.language == language,
            PipelineJob.job_type == "summarise",
        )
        .order_by(PipelineJob.id.desc())
        .limit(1)
    )
    job = job_result.scalar_one_or_none()

    return SummarisationStatus(
        linear_id=linear_id,
        summarisation_status=summary.summarisation_status,
        job_id=job.id if job else None,
        job_status=job.status if job else None,
        error=job.error if job else None,
    )


@router.get("/{linear_id}/copyright-report", response_model=CopyrightReport)
async def get_copyright_report(
    linear_id: str,
    language: str = "english",
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Summary).where(
            Summary.linear_id == linear_id, Summary.language == language
        )
    )
    summary = result.scalar_one_or_none()
    if not summary:
        raise HTTPException(404, f"Summary {linear_id} not found")

    report = summary.copyright_report or {}
    return CopyrightReport(
        linear_id=linear_id,
        copyright_status=report.get("copyright_status"),
        violations=report.get("violations", []),
    )


@router.post("/{linear_id}/approve", status_code=200)
async def approve(
    linear_id: str,
    language: str = "english",
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Summary).where(
            Summary.linear_id == linear_id, Summary.language == language
        )
    )
    summary = result.scalar_one_or_none()
    if not summary:
        raise HTTPException(404, f"Summary {linear_id} not found")
    if summary.summarisation_status not in ("copyright_passed", "copyright_failed"):
        raise HTTPException(
            409,
            f"Cannot approve — summarisation_status is '{summary.summarisation_status}', expected copyright_passed or copyright_failed",
        )

    # Use revised summary if available, fall back to final_summary
    production_summary = summary.copyright_revised_summary or summary.final_summary
    await session.execute(
        update(Summary)
        .where(Summary.linear_id == linear_id, Summary.language == language)
        .values(
            voice_status="voice_text",
            final_summary=production_summary,
        )
    )
    await session.commit()
    return {"linear_id": linear_id, "voice_status": "voice_text"}

# backend/routers/pipeline.py
import asyncio
from datetime import datetime, timezone
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database import get_session, SessionLocal
from backend.models import Summary, PipelineJob
from backend.schemas import JobCreate, JobStatus
from backend.services.voice_service import generate_voice_text
from backend.services.audio_service import generate_audio

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])

async def _run_job(job_id: int, job: JobCreate) -> None:
    async with SessionLocal() as session:
        await session.execute(
            update(PipelineJob)
            .where(PipelineJob.id == job_id)
            .values(status="running", started_at=datetime.now(timezone.utc))
        )
        await session.commit()

        try:
            result = await session.execute(
                select(Summary).where(
                    Summary.linear_id == job.linear_id,
                    Summary.language == job.language,
                )
            )
            summary = result.scalar_one_or_none()
            if not summary:
                raise ValueError(f"Summary {job.linear_id}/{job.language} not found")

            if job.job_type == "voice_text":
                ok = await asyncio.to_thread(
                    generate_voice_text,
                    summary.linear_id, summary.language,
                    summary.title, summary.final_summary or ""
                )
                if ok:
                    summary.voice_status = "voice_text"
                    summary.voice_text_generated_at = datetime.now(timezone.utc)
                else:
                    raise ValueError("generate_voice_text returned False — no output produced")

            elif job.job_type == "audio":
                url = await asyncio.to_thread(
                    generate_audio,
                    summary.linear_id, summary.language, summary.voice_id
                )
                if url:
                    summary.voice_status = "voice"
                    summary.audio_url = url
                    summary.audio_generated_at = datetime.now(timezone.utc)
                    summary.supabase_uploaded = True
                else:
                    raise ValueError("generate_audio returned None — audio generation failed")

            elif job.job_type == "upload":
                raise NotImplementedError("upload job type not yet implemented")

            await session.execute(
                update(PipelineJob)
                .where(PipelineJob.id == job_id)
                .values(status="done", completed_at=datetime.now(timezone.utc))
            )
            await session.commit()

        except Exception as exc:
            await session.rollback()
            await session.execute(
                update(PipelineJob)
                .where(PipelineJob.id == job_id)
                .values(status="failed", error=str(exc), completed_at=datetime.now(timezone.utc))
            )
            await session.commit()

@router.post("/trigger", response_model=JobStatus, status_code=202)
async def trigger_job(
    body: JobCreate,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
):
    job = PipelineJob(
        linear_id=body.linear_id,
        language=body.language,
        job_type=body.job_type,
        status="pending",
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    background_tasks.add_task(_run_job, job.id, body)
    return JobStatus.model_validate(job)

@router.get("/jobs/{job_id}", response_model=JobStatus)
async def get_job(job_id: int, session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(PipelineJob).where(PipelineJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(404, "Job not found")
    return JobStatus.model_validate(job)

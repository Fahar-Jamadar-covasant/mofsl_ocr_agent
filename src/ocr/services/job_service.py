"""
OCRJobService — create and update OCR job records in the database.

Responsibilities:
- Create a new OCRJob row when a workflow run begins.
- Update status as the workflow progresses.
- Record parsed_json_path once storage is complete.
- Mark a job completed or failed.

No parsing or extraction logic lives here.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cams_otel_lib import Logger as logger, otel_trace
from src.ocr.storage.database import get_session_factory
from src.ocr.storage.models import OCRJob


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class OCRJobService:

    @otel_trace
    def __init__(self) -> None:
        self._factory = get_session_factory()

    # ── Public API ────────────────────────────────────────────────────────────

    @otel_trace
    async def create_job(
        self,
        thread_id: str,
        process_type: str,
        document_name: Optional[str] = None,
        s3_object_key: Optional[str] = None,
        textract_job_id: Optional[str] = None,
    ) -> OCRJob:
        """Insert a new OCRJob row and return the persisted object."""
        async with self._factory() as session:
            job = OCRJob(
                thread_id=thread_id,
                process_type=process_type,
                status="pending",
                document_name=document_name,
                s3_object_key=s3_object_key,
                textract_job_id=textract_job_id,
            )
            session.add(job)
            await session.commit()
            await session.refresh(job)

        logger.info(
            f"OCRJob created — id={job.id}, thread_id={thread_id!r}, "
            f"process_type={process_type!r}"
        )
        return job

    @otel_trace
    async def update_status(self, job_id: int, status: str) -> None:
        """Update the status of an existing OCRJob row."""
        async with self._factory() as session:
            job = await self._get_job(session, job_id)
            if job is None:
                logger.warning(f"OCRJobService.update_status: job_id={job_id} not found")
                return
            job.status = status
            job.updated_at = _utcnow()
            await session.commit()

        logger.debug(f"OCRJob status updated — id={job_id}, status={status!r}")

    @otel_trace
    async def update_parsed_json_path(self, job_id: int, parsed_json_path: str) -> None:
        """Store the local file path where extracted JSON was persisted."""
        async with self._factory() as session:
            job = await self._get_job(session, job_id)
            if job is None:
                logger.warning(f"OCRJobService.update_parsed_json_path: job_id={job_id} not found")
                return
            job.parsed_json_path = parsed_json_path
            job.updated_at = _utcnow()
            await session.commit()

        logger.debug(f"OCRJob parsed_json_path updated — id={job_id}, path={parsed_json_path!r}")

    @otel_trace
    async def mark_completed(self, job_id: int, parsed_json_path: Optional[str] = None) -> None:
        """Mark a job as completed, optionally recording the output path."""
        async with self._factory() as session:
            job = await self._get_job(session, job_id)
            if job is None:
                logger.warning(f"OCRJobService.mark_completed: job_id={job_id} not found")
                return
            job.status = "completed"
            job.completed_at = _utcnow()
            job.updated_at = _utcnow()
            if parsed_json_path is not None:
                job.parsed_json_path = parsed_json_path
            await session.commit()

        logger.info(f"OCRJob marked completed — id={job_id}")

    @otel_trace
    async def mark_failed(self, job_id: int, reason: Optional[str] = None) -> None:
        """Mark a job as failed."""
        async with self._factory() as session:
            job = await self._get_job(session, job_id)
            if job is None:
                logger.warning(f"OCRJobService.mark_failed: job_id={job_id} not found")
                return
            job.status = "failed"
            job.updated_at = _utcnow()
            await session.commit()

        logger.warning(f"OCRJob marked failed — id={job_id}, reason={reason!r}")

    # ── Private helpers ───────────────────────────────────────────────────────

    @staticmethod
    async def _get_job(session: AsyncSession, job_id: int) -> Optional[OCRJob]:
        result = await session.execute(select(OCRJob).where(OCRJob.id == job_id))
        return result.scalar_one_or_none()

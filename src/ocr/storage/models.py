"""
SQLAlchemy ORM model for the ocr_jobs table.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.ocr.storage.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class OCRJob(Base):
    __tablename__ = "ocr_jobs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    thread_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    process_type: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="pending")

    document_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    s3_object_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    textract_job_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    parsed_json_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return (
            f"OCRJob(id={self.id}, thread_id={self.thread_id!r}, "
            f"process_type={self.process_type!r}, status={self.status!r})"
        )

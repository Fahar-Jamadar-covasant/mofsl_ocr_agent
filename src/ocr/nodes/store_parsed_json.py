"""
StoreParsedJson — persists extracted_data to local storage and updates the OCR Job record.
"""

from typing import Any, Dict, Optional

from cams_otel_lib import otel_trace
from src.config.settings import settings
from src.ocr.storage.storage_service import StorageService
from src.ocr.utils.ocr_logger import step_start, step_done, step_error, step_warn


class StoreParsedJsonNode:

    @otel_trace
    def __init__(self, config: Dict[str, Any], tenant_id: str = "default") -> None:
        self.config = config
        self.tenant_id = tenant_id
        self._storage = StorageService()

    @otel_trace
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        document: str = state.get("document", "document")
        process_type: str = state.get("process_type", "unknown")
        extracted_data: Dict[str, Any] = state.get("extracted_data") or {}
        thread_id: str = state.get("thread_id", "unknown")
        s3_object_key: Optional[str] = state.get("s3_object_key")
        textract_job_id: Optional[str] = state.get("textract_job_id")

        t = step_start("StoreParsedJson", process_type=process_type, document=document)

        ocr_job_id: Optional[int] = None
        if settings.postgres_connection_string:
            ocr_job_id = await self._create_job(
                thread_id=thread_id,
                process_type=process_type,
                document_name=document,
                s3_object_key=s3_object_key,
                textract_job_id=textract_job_id,
            )
        else:
            step_warn("StoreParsedJson", "postgres not configured — skipping job record")

        try:
            parsed_json_path = await self._storage.save_extracted_data(
                extracted_data=extracted_data,
                process_type=process_type,
                document_name=document,
            )
        except Exception as exc:
            step_error("StoreParsedJson", str(exc), elapsed=t.elapsed())
            raise

        if ocr_job_id is not None:
            await self._complete_job(ocr_job_id, parsed_json_path)

        step_done(
            "StoreParsedJson",
            elapsed=t.elapsed(),
            path=parsed_json_path,
            job_id=ocr_job_id,
        )

        return {
            "parsed_json_path": parsed_json_path,
            "ocr_job_id": ocr_job_id,
            "status": "stored",
            "metadata": {
                **state.get("metadata", {}),
                "parsed_json_path": parsed_json_path,
                "ocr_job_id": ocr_job_id,
            },
        }

    async def _create_job(
        self,
        thread_id: str,
        process_type: str,
        document_name: str,
        s3_object_key: Optional[str],
        textract_job_id: Optional[str],
    ) -> Optional[int]:
        try:
            from src.ocr.services.job_service import OCRJobService
            svc = OCRJobService()
            job = await svc.create_job(
                thread_id=thread_id,
                process_type=process_type,
                document_name=document_name,
                s3_object_key=s3_object_key,
                textract_job_id=textract_job_id,
            )
            await svc.update_status(job.id, "running")
            return job.id
        except Exception as exc:
            step_warn("StoreParsedJson", f"failed to create OCRJob — {exc}")
            return None

    async def _complete_job(self, job_id: int, parsed_json_path: str) -> None:
        try:
            from src.ocr.services.job_service import OCRJobService
            svc = OCRJobService()
            await svc.mark_completed(job_id, parsed_json_path=parsed_json_path)
        except Exception as exc:
            step_warn("StoreParsedJson", f"failed to mark OCRJob completed — {exc}")

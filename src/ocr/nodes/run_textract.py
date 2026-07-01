"""
RunTextract — submits the S3 document to Amazon Textract and waits for the result.
"""

from typing import Any, Dict

from cams_otel_lib import Logger as logger, otel_trace
from src.ocr.services.textract_service import TextractService
from src.ocr.utils.ocr_logger import step_start, step_done, step_error


class RunTextractNode:

    @otel_trace
    def __init__(self, config: Dict[str, Any], tenant_id: str = "default") -> None:
        self.config = config
        self.tenant_id = tenant_id
        self._textract = TextractService()

    @otel_trace
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        s3_object_key: str = state.get("s3_object_key", "")

        t = step_start("RunTextract", s3_object_key=s3_object_key)

        try:
            job_id, merged_response = await self._textract.analyze_document(s3_object_key)
        except Exception as exc:
            step_error("RunTextract", str(exc), elapsed=t.elapsed())
            raise

        block_count = len(merged_response.get("Blocks", []))
        step_done("RunTextract", elapsed=t.elapsed(), job_id=job_id, blocks=block_count)

        return {
            "textract_job_id": job_id,
            "raw_textract_response": merged_response,
            "status": "ocr_complete",
            "metadata": {
                **state.get("metadata", {}),
                "textract_job_id": job_id,
                "textract_block_count": block_count,
            },
        }

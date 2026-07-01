"""
UploadToS3 — uploads the source document to S3 before Textract processing.
"""

from typing import Any, Dict

from cams_otel_lib import Logger as logger, otel_trace
from src.ocr.services.s3_service import S3Service
from src.ocr.utils.ocr_logger import step_start, step_done, step_error


class UploadToS3Node:

    @otel_trace
    def __init__(self, config: Dict[str, Any], tenant_id: str = "default") -> None:
        self.config = config
        self.tenant_id = tenant_id
        self._s3 = S3Service()

    @otel_trace
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        document: str = state.get("document", "")

        t = step_start("UploadToS3", document=document, bucket=self._s3.bucket_name)

        try:
            s3_object_key = await self._s3.upload_document(document)
        except Exception as exc:
            step_error("UploadToS3", str(exc), elapsed=t.elapsed())
            raise

        step_done("UploadToS3", elapsed=t.elapsed(), s3_object_key=s3_object_key)

        return {
            "s3_object_key": s3_object_key,
            "status": "uploaded",
            "metadata": {
                **state.get("metadata", {}),
                "s3_object_key": s3_object_key,
            },
        }

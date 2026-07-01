"""
ReturnStructuredOutput — constructs the final OCRResponse from accumulated state.
"""

from typing import Any, Dict

from cams_otel_lib import otel_trace
from src.ocr.models.ocr_response import OCRResponse
from src.ocr.utils.ocr_logger import step_start, step_done


class ReturnStructuredOutputNode:

    @otel_trace
    def __init__(self, config: Dict[str, Any], tenant_id: str = "default") -> None:
        self.config = config
        self.tenant_id = tenant_id

    @otel_trace
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        process_type = state.get("process_type", "unknown")
        extracted_data = state.get("extracted_data") or {}
        metadata = state.get("metadata") or {}
        error: str | None = state.get("error")

        t = step_start("ReturnStructuredOutput", process_type=process_type, success=error is None)

        response = OCRResponse(
            success=error is None,
            process_type=process_type,
            extracted_data=extracted_data,
            metadata={
                **metadata,
                "s3_object_key": state.get("s3_object_key"),
                "textract_job_id": state.get("textract_job_id"),
                "parsed_json_path": state.get("parsed_json_path"),
                "ocr_job_id": state.get("ocr_job_id"),
                "final_status": state.get("status"),
            },
            error=error,
        )

        step_done(
            "ReturnStructuredOutput",
            elapsed=t.elapsed(),
            success=response.success,
            fields=len(extracted_data),
        )

        return {
            "response": response,
            "status": "complete",
        }

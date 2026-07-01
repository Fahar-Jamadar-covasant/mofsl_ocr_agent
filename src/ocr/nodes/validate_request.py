"""
ValidateRequest — first node in the OCR LangGraph workflow.
"""

from typing import Any, Dict

from cams_otel_lib import Logger as logger, otel_trace
from src.ocr.process.factory import OCRProcessFactory
from src.ocr.utils.ocr_logger import step_start, step_done, step_error


class ValidateRequestNode:

    @otel_trace
    def __init__(self, config: Dict[str, Any], tenant_id: str = "default") -> None:
        self.config = config
        self.tenant_id = tenant_id

    @otel_trace
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        document: str = state.get("document", "")
        process_type: str = state.get("process_type", "")

        t = step_start("ValidateRequest", document=document, process_type=process_type)

        if not document or not document.strip():
            error = "document must not be empty"
            step_error("ValidateRequest", error, elapsed=t.elapsed())
            return {"status": "error", "error": error}

        try:
            OCRProcessFactory.resolve(process_type)
        except ValueError as exc:
            error = str(exc)
            step_error("ValidateRequest", error, elapsed=t.elapsed())
            return {"status": "error", "error": error}

        step_done("ValidateRequest", elapsed=t.elapsed(), process_type=process_type)

        return {
            "status": "validated",
            "metadata": {
                **state.get("metadata", {}),
                "validated": True,
                "document": document.strip(),
                "process_type": process_type,
            },
        }

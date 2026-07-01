"""
ParseOCRDocument — converts the raw Textract response into a structured document.
"""

from typing import Any, Dict

from cams_otel_lib import Logger as logger, otel_trace
from src.ocr.parser import OCRDocumentParser
from src.ocr.utils.ocr_logger import step_start, step_done, step_error


class ParseOCRDocumentNode:

    @otel_trace
    def __init__(self, config: Dict[str, Any], tenant_id: str = "default") -> None:
        self.config = config
        self.tenant_id = tenant_id

    @otel_trace
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        raw_textract_response: Dict[str, Any] = state.get("raw_textract_response") or {}
        job_id = state.get("textract_job_id", "unknown")
        block_count = len(raw_textract_response.get("Blocks", []))

        t = step_start("ParseOCRDocument", job_id=job_id, blocks=block_count)

        try:
            parser = OCRDocumentParser(raw_textract_response)
            parsed_document = await parser.parse()
        except Exception as exc:
            step_error("ParseOCRDocument", str(exc), elapsed=t.elapsed())
            raise

        page_count = parsed_document.get("page_count", 0)
        step_done("ParseOCRDocument", elapsed=t.elapsed(), pages=page_count)

        return {
            "parsed_document": parsed_document,
            "status": "parsed",
            "metadata": {
                **state.get("metadata", {}),
                "parsed": True,
                "page_count": page_count,
            },
        }

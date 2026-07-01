"""
ResolveProcess — resolves the correct OCRProcess implementation for this run.
"""

from typing import Any, Dict

from cams_otel_lib import Logger as logger, otel_trace
from src.ocr.process.factory import OCRProcessFactory
from src.ocr.utils.ocr_logger import step_start, step_done, step_error


class ResolveProcessNode:

    @otel_trace
    def __init__(self, config: Dict[str, Any], tenant_id: str = "default") -> None:
        self.config = config
        self.tenant_id = tenant_id

    @otel_trace
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        process_type: str = state.get("process_type", "")

        t = step_start("ResolveProcess", process_type=process_type)

        try:
            process = OCRProcessFactory.resolve(process_type)
        except Exception as exc:
            step_error("ResolveProcess", str(exc), elapsed=t.elapsed())
            raise

        step_done("ResolveProcess", elapsed=t.elapsed(), resolved=type(process).__name__)

        # Do NOT store the process object in state — msgpack (AsyncPostgresSaver)
        # cannot serialize arbitrary Python objects. process_type is already in
        # state as a plain string; StructuredExtractionNode resolves it on the fly.
        return {
            "status": "process_resolved",
            "metadata": {
                **state.get("metadata", {}),
                "process_type": process_type,
                "process_class": type(process).__name__,
            },
        }

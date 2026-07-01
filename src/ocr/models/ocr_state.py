"""
OCR LangGraph state definition.
"""

from typing import Any, Dict, Optional
from typing_extensions import TypedDict

from .ocr_request import OCRRequest
from .ocr_response import OCRResponse
from src.ocr.process.base import OCRProcess


class OCRState(TypedDict):
    """
    State carried through the OCR LangGraph workflow.

    Fields are intentionally typed with Optional/Any placeholders for fields
    whose real types will be defined when the producing node is implemented.

    Lifecycle
    ---------
    status  : coarse execution stage set by each node
              ("pending" → "validated" → "uploaded" → "ocr_running" →
               "ocr_complete" → "parsed" → "process_resolved" →
               "extracted" → "stored" → "complete" | "error")
    error   : human-readable error message; set on any fatal node failure.

    Data fields
    -----------
    request              : original caller input
    process_type         : denormalised from request for convenience
    document             : denormalised document identifier from request
    s3_object_key        : S3 key after the document is uploaded (Phase 3)
    textract_job_id      : AWS Textract async job ID (Phase 3)
    raw_textract_response: raw Textract API payload (Phase 3)
    parsed_document      : Textract output parsed into an intermediate structure
                           (Phase 3 / 4)
    process              : process object resolved from process_type (Phase 4)
    extracted_data       : structured extraction result (Phase 4)
    parsed_json_path     : local path where extracted_data was persisted
                           (Phase 5)
    response             : final OCRResponse returned to the caller; populated
                           exclusively by ReturnStructuredOutput.
    metadata             : arbitrary key-value audit / diagnostic data
                           accumulated across nodes.

    Framework fields
    ----------------
    tenant_id : resolved tenant; used for config lookup.
    thread_id : LangGraph checkpoint key for multi-turn continuity.
    """

    # ── Input ────────────────────────────────────────────────────────────────
    request: OCRRequest
    process_type: str
    document: str

    # ── S3 ───────────────────────────────────────────────────────────────────
    s3_object_key: Optional[str]

    # ── Textract ─────────────────────────────────────────────────────────────
    textract_job_id: Optional[str]
    raw_textract_response: Optional[Dict[str, Any]]

    # ── Parsing ───────────────────────────────────────────────────────────────
    parsed_document: Optional[Dict[str, Any]]

    # ── Process resolution ────────────────────────────────────────────────────
    process: Optional[OCRProcess]

    # ── Extraction ────────────────────────────────────────────────────────────
    extracted_data: Optional[Dict[str, Any]]

    # ── Storage ───────────────────────────────────────────────────────────────
    parsed_json_path: Optional[str]
    ocr_job_id: Optional[int]

    # ── Output ────────────────────────────────────────────────────────────────
    response: Optional[OCRResponse]

    # ── Lifecycle ─────────────────────────────────────────────────────────────
    metadata: Dict[str, Any]
    status: str
    error: Optional[str]

    # ── Framework ─────────────────────────────────────────────────────────────
    tenant_id: str
    thread_id: str

"""
OCR request model with field-level validation.
"""

from typing import Optional
from pydantic import BaseModel, field_validator


class OCRRequest(BaseModel):
    """
    Input contract for the OCR Agent.

    Fields:
        document        — document identifier or S3 key. Must be non-empty.
        process_type    — processing variant (e.g. "individual_account_opening").
                          Must match a registered process in OCRProcessFactory.
        conversation_id — optional caller-supplied thread identifier for checkpoint
                          resume. Auto-generated when omitted.
    """

    document: str
    process_type: str
    conversation_id: Optional[str] = None

    @field_validator("document")
    @classmethod
    def document_must_not_be_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("document must not be empty or blank")
        return v.strip()

    @field_validator("process_type")
    @classmethod
    def process_type_must_be_registered(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("process_type must not be empty or blank")
        # Lazy import avoids circular dependency at module load time.
        from src.ocr.process.factory import _REGISTRY
        v = v.strip()
        if v not in _REGISTRY:
            supported = ", ".join(sorted(_REGISTRY))
            raise ValueError(
                f"Unknown process_type={v!r}. Supported values: {supported}"
            )
        return v

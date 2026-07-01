"""
OCR response model.
"""

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class OCRResponse(BaseModel):
    """
    Output contract for the OCR Agent.

    Fields:
        success        — whether the workflow completed without a fatal error.
        process_type   — echoes the requested process type for traceability.
        extracted_data — structured extraction result (empty on failure).
        metadata       — diagnostic / audit information about the run.
        error          — human-readable error message when success is False;
                         None on success.
    """

    success: bool
    process_type: str
    extracted_data: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None

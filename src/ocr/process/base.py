"""
OCRProcess — abstract base class for all OCR document processing strategies.

Every concrete process must:
- Declare a unique process_type identifier.
- Expose the path to its extraction prompt (loaded by StructuredExtractionNode).
- Expose its Pydantic output schema class (used with with_structured_output()).

The process does not load prompts or call the LLM — it only provides metadata.

Checkpoint serialization
------------------------
LangGraph's AsyncPostgresSaver serializes graph state using JsonPlusSerializer,
which falls back to pickle for Python objects stored in state fields.  The
default pickle protocol reconstructs an object by importing its class and
calling __new__ / __setstate__, which means the import path must remain stable
across deployments.

To avoid that fragility we override __reduce__ so that pickle always
reconstructs an OCRProcess by calling OCRProcessFactory.resolve(process_type)
rather than directly importing the concrete class.  The lazy import inside
_restore_ocr_process_from_type prevents the circular import that would arise
from importing factory.py at module load time.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Tuple, Type

from pydantic import BaseModel


# ── Pickle restoration helper ─────────────────────────────────────────────────
# Must be a module-level function so pickle can locate it by dotted name.

def _restore_ocr_process_from_type(process_type: str) -> "OCRProcess":
    """Reconstruct an OCRProcess from its process_type string via the factory."""
    from src.ocr.process.factory import OCRProcessFactory  # lazy — avoids circular import
    return OCRProcessFactory.resolve(process_type)


# ── Abstract base ─────────────────────────────────────────────────────────────

class OCRProcess(ABC):

    @property
    @abstractmethod
    def process_type(self) -> str:
        """Unique string identifier for this process, e.g. 'individual_account_opening'."""

    @property
    @abstractmethod
    def prompt_path(self) -> Path:
        """Absolute path to the Markdown prompt file for this process."""

    @property
    @abstractmethod
    def output_schema(self) -> Type[BaseModel]:
        """Pydantic model class used as the structured-output target for LLM extraction."""

    # ── Pickle protocol ───────────────────────────────────────────────────────

    def __reduce__(self) -> Tuple:
        """
        Control how this object is pickled.

        When AsyncPostgresSaver deserializes a checkpoint, it calls
        _restore_ocr_process_from_type(process_type) which re-creates the
        correct OCRProcess subclass via OCRProcessFactory.  This keeps
        deserialization stable regardless of class renames or module moves.
        """
        return (_restore_ocr_process_from_type, (self.process_type,))

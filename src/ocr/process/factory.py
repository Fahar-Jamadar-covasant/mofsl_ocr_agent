"""
OCRProcessFactory — resolves a process_type string to an OCRProcess instance.

Adding a new process requires only:
1. Create a new OCRProcess subclass.
2. Register it in _REGISTRY below.

No changes to LangGraph nodes or the workflow are needed.
"""

from typing import Dict, Type

from src.ocr.process.base import OCRProcess
from src.ocr.process.individual_account_opening import IndividualAccountOpeningProcess

_REGISTRY: Dict[str, Type[OCRProcess]] = {
    "individual_account_opening": IndividualAccountOpeningProcess,
}


class OCRProcessFactory:

    @staticmethod
    def resolve(process_type: str) -> OCRProcess:
        """
        Return an OCRProcess instance for the given process_type.

        Raises:
            ValueError: when process_type is not registered.
        """
        cls = _REGISTRY.get(process_type)
        if cls is None:
            supported = ", ".join(sorted(_REGISTRY))
            raise ValueError(
                f"Unknown process_type={process_type!r}. "
                f"Supported: {supported}"
            )
        return cls()

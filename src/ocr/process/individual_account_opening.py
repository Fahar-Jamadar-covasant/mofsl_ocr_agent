from pathlib import Path
from typing import Type

from pydantic import BaseModel

from src.ocr.process.base import OCRProcess
from src.ocr.schemas.individual_account_opening import IndividualAccountOpeningData

# Prompts live alongside the schemas under src/ocr/
_PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


class IndividualAccountOpeningProcess(OCRProcess):

    @property
    def process_type(self) -> str:
        return "individual_account_opening"

    @property
    def prompt_path(self) -> Path:
        return _PROMPTS_DIR / "individual_account_opening.md"

    @property
    def output_schema(self) -> Type[BaseModel]:
        return IndividualAccountOpeningData

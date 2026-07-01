"""
OCR process package — factory-based process resolution.
"""

from .base import OCRProcess
from .factory import OCRProcessFactory

__all__ = ["OCRProcess", "OCRProcessFactory"]

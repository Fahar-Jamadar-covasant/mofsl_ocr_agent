"""
OCR parser package — wraps the Textract block-level parser into a clean async API.
"""

from .ocr_document_parser import OCRDocumentParser

__all__ = ["OCRDocumentParser"]

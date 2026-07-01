"""
OCRDocumentParser — high-level entry point for the OCR parsing pipeline.

Wraps TextractParser so that nodes only need one call:
    OCRDocumentParser(raw_textract_response).parse()

Returns a plain dict ready to be stored in OCRState.parsed_document:
    {
        "pages": [ { "page": 1, "lines": [...], "tables": [...], ... }, ... ],
        "page_count": N,
    }
"""

import asyncio
from typing import Any, Dict

from cams_otel_lib import Logger as logger, otel_trace

from src.ocr.parser.textract_parser import TextractParser


class OCRDocumentParser:

    @otel_trace
    def __init__(self, raw_textract_response: Dict[str, Any]) -> None:
        self._parser = TextractParser(raw_textract_response)

    @otel_trace
    async def parse(self) -> Dict[str, Any]:
        """
        Parse all pages and return structured dict.

        TextractParser.parse_all() is synchronous (pure Python, no I/O), so it
        is run in a thread to keep the event loop free for large documents.
        """
        page_results = await asyncio.to_thread(self._parser.parse_all)

        pages = [pr.to_dict() for pr in page_results]

        logger.info(
            f"OCRDocumentParser complete — "
            f"pages={len(pages)}, "
            f"total_lines={sum(len(p['lines']) for p in pages)}, "
            f"total_tables={sum(len(p['tables']) for p in pages)}"
        )

        return {
            "pages": pages,
            "page_count": len(pages),
        }

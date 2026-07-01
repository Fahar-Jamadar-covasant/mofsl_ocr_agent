"""
Backward-compatibility shim — redirects to src.ocr.graph.workflow.

The canonical location of the OCR graph is src/ocr/graph/workflow.py.
This module exists only so that any import of src.ocr.workflow continues
to work without changes.
"""

from src.ocr.graph.workflow import build_ocr_graph  # noqa: F401

__all__ = ["build_ocr_graph"]

"""
OCR LangGraph workflow definition.

Builds the complete OCR StateGraph.  The executor delegates graph construction
here so workflow topology is decoupled from server wiring.

Phase 2 topology (sequential):

    START
      ↓
    validate_request
      ↓
    upload_to_s3
      ↓
    run_textract
      ↓
    parse_ocr_document
      ↓
    resolve_process
      ↓
    structured_extraction
      ↓
    store_parsed_json
      ↓
    return_structured_output
      ↓
    END

Adding error-handling edges, conditional branches, or retry loops in later
phases requires only changes to this file — the nodes and the executor are
not affected.
"""

from typing import Any, Dict

from langgraph.graph import END, StateGraph

from cams_otel_lib import Logger as logger, otel_trace

from src.ocr.models.ocr_state import OCRState
from src.ocr.nodes import (
    ValidateRequestNode,
    UploadToS3Node,
    RunTextractNode,
    ParseOCRDocumentNode,
    ResolveProcessNode,
    StructuredExtractionNode,
    StoreParsedJsonNode,
    ReturnStructuredOutputNode,
)

# Node name constants — referenced in workflow.py only; nodes are unaware of
# their graph names so they remain independently testable.
_N_VALIDATE = "validate_request"
_N_UPLOAD = "upload_to_s3"
_N_TEXTRACT = "run_textract"
_N_PARSE = "parse_ocr_document"
_N_RESOLVE = "resolve_process"
_N_EXTRACT = "structured_extraction"
_N_STORE = "store_parsed_json"
_N_RETURN = "return_structured_output"


@otel_trace
def build_ocr_graph(config: Dict[str, Any], tenant_id: str = "default") -> StateGraph:
    """
    Construct and return the OCR StateGraph (not yet compiled).

    Compilation (attaching a checkpointer) is handled by the executor so it
    can apply the same PostgreSQL / MemorySaver decision used for the main
    agent graph.

    Args:
        config:    Full internal config dict (as produced by load_agent_config).
        tenant_id: Tenant identifier for node-level config lookup.

    Returns:
        Uncompiled StateGraph[OCRState].
    """
    workflow: StateGraph = StateGraph(OCRState)

    # ── Register nodes ────────────────────────────────────────────────────────
    workflow.add_node(_N_VALIDATE, ValidateRequestNode(config, tenant_id).execute)
    workflow.add_node(_N_UPLOAD,   UploadToS3Node(config, tenant_id).execute)
    workflow.add_node(_N_TEXTRACT, RunTextractNode(config, tenant_id).execute)
    workflow.add_node(_N_PARSE,    ParseOCRDocumentNode(config, tenant_id).execute)
    workflow.add_node(_N_RESOLVE,  ResolveProcessNode(config, tenant_id).execute)
    workflow.add_node(_N_EXTRACT,  StructuredExtractionNode(config, tenant_id).execute)
    workflow.add_node(_N_STORE,    StoreParsedJsonNode(config, tenant_id).execute)
    workflow.add_node(_N_RETURN,   ReturnStructuredOutputNode(config, tenant_id).execute)

    # ── Sequential edges ──────────────────────────────────────────────────────
    workflow.set_entry_point(_N_VALIDATE)
    workflow.add_edge(_N_VALIDATE, _N_UPLOAD)
    workflow.add_edge(_N_UPLOAD,   _N_TEXTRACT)
    workflow.add_edge(_N_TEXTRACT, _N_PARSE)
    workflow.add_edge(_N_PARSE,    _N_RESOLVE)
    workflow.add_edge(_N_RESOLVE,  _N_EXTRACT)
    workflow.add_edge(_N_EXTRACT,  _N_STORE)
    workflow.add_edge(_N_STORE,    _N_RETURN)
    workflow.add_edge(_N_RETURN,   END)

    logger.info(
        f"OCR graph constructed for tenant={tenant_id} "
        f"(Phase 2 — {8}-node sequential pipeline)"
    )
    return workflow

"""
StructuredExtraction — extracts typed fields from the parsed OCR document using an LLM.

Uses a plain chat/completions call (no function-calling / tool-use format) so the
request is compatible with any OpenAI-compatible gateway regardless of the underlying
model.  The LLM is prompted to return raw JSON; the response is extracted with a regex
and validated with the process Pydantic schema.
"""

import json
import re
from typing import Any, Dict, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import ValidationError

from cams_otel_lib import otel_trace
from src.config.agent_config import get_node_configuration
from src.utils.llm_provider import get_llm_model, get_provider_from_model
from src.ocr.process.base import OCRProcess
from src.ocr.process.factory import OCRProcessFactory
from src.ocr.storage.storage_service import StorageService
from src.ocr.utils.ocr_logger import step_start, step_done, step_error, step_warn

# Maximum pages sent to the LLM in a single call.
# 61-page documents with 40k+ blocks exceed the LiteLLM gateway limit.
# Account opening forms concentrate key fields in the first pages.
_MAX_PAGES = 10


class StructuredExtractionNode:

    @otel_trace
    def __init__(self, config: Dict[str, Any], tenant_id: str = "default") -> None:
        self.config = config
        self.tenant_id = tenant_id

        self.node_config = get_node_configuration("extraction", tenant_id, config)
        tenant_config = config.get(tenant_id, config.get("default", {}))
        llm_config = tenant_config.get("llm_config", {}).get("extraction", {})

        self.model = llm_config.get("model", "gpt-4o")
        self.temperature = llm_config.get("temperature", 0.1)
        self.max_tokens = llm_config.get("max_tokens", None)
        self.provider = llm_config.get("provider")

        if not self.provider:
            try:
                self.provider = get_provider_from_model(self.model)
            except ValueError:
                self.provider = "openai"

        self._storage = StorageService()

    @otel_trace
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        process_type: str = state.get("process_type", "")
        process = OCRProcessFactory.resolve(process_type)

        parsed_document: Dict[str, Any] = state.get("parsed_document") or {}
        page_count = parsed_document.get("page_count", 0)

        # Truncate to _MAX_PAGES to stay within LLM context/token limits
        truncated_document, sent_pages = self._truncate_document(parsed_document)
        if sent_pages < page_count:
            step_warn(
                "StructuredExtraction",
                f"Document has {page_count} pages — sending first {sent_pages} to stay within token limit",
            )

        t = step_start(
            "StructuredExtraction",
            process_type=process.process_type,
            pages_total=page_count,
            pages_sent=sent_pages,
            model=self.model,
            provider=str(self.provider),
        )

        system_prompt = self._load_prompt(process)

        # Persist the compacted document before the LLM call so it can be
        # inspected offline even when the call fails.
        document: str = state.get("document", "document")
        compact_doc = self._compact_document(truncated_document)
        try:
            parsed_doc_path = await self._storage.save_parsed_document(
                parsed_document=compact_doc,
                process_type=process_type,
                document_name=document,
            )
            step_warn("StructuredExtraction", f"parsed document saved → {parsed_doc_path}")
        except Exception as save_exc:
            step_warn("StructuredExtraction", f"could not save parsed document: {save_exc}")

        user_message = self._build_user_message(truncated_document)
        step_warn(
            "StructuredExtraction",
            f"payload size: system={len(system_prompt):,} chars  "
            f"user={len(user_message):,} chars  "
            f"total={len(system_prompt) + len(user_message):,} chars",
        )

        custom_headers = state.get("litellm_headers")
        llm = get_llm_model(
            provider=self.provider,
            model_name=self.model,
            temperature=self.temperature,
            streaming=False,
            max_tokens=self.max_tokens,
            custom_headers=custom_headers,
        )

        # ── Plain chat/completions — no function-calling or tool-use format ──────
        # with_structured_output() emits OpenAI function-calling payload which the
        # LiteLLM gateway cannot translate for Gemini models, producing HTTP 500.
        # Instead: invoke the LLM directly, extract the JSON block from the response
        # text, then validate it with the process Pydantic schema.
        try:
            response = await llm.ainvoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_message),
            ])
            raw_content: str = (
                response.content if hasattr(response, "content") else str(response)
            )
        except Exception as exc:
            step_error(
                "StructuredExtraction",
                f"LLM call failed: {type(exc).__name__}: {exc}",
                elapsed=t.elapsed(),
            )
            return self._empty_result(state, t, process=process, error=str(exc))

        step_warn(
            "StructuredExtraction",
            f"LLM response received: {len(raw_content):,} chars",
        )
        step_warn("StructuredExtraction", f"LLM raw response:\n{raw_content}")

        extracted_data = self._parse_llm_response(raw_content, process)
        if extracted_data is None:
            step_error(
                "StructuredExtraction",
                "JSON extraction/validation failed — returning empty schema",
                elapsed=t.elapsed(),
            )
            return self._empty_result(
                state, t, process=process,
                error="JSON extraction/validation failed",
            )

        step_done(
            "StructuredExtraction",
            elapsed=t.elapsed(),
            keys=list(extracted_data.keys()),
        )

        return {
            "extracted_data": extracted_data,
            "status": "extracted",
            "metadata": {
                **state.get("metadata", {}),
                "extraction_complete": True,
                "extraction_model": self.model,
                "extraction_provider": str(self.provider),
                "pages_sent_to_llm": sent_pages,
                "pages_total": page_count,
            },
        }

    # ── Private helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _parse_llm_response(
        raw_content: str,
        process: OCRProcess,
    ) -> Optional[Dict[str, Any]]:
        """Extract the JSON object from the LLM response and validate it.

        Extraction order:
        1. Fenced code block  ```json { ... } ```  (greedy — captures full object)
        2. Fenced code block  ``` { ... } ```
        3. Outermost bare { ... } in the text

        After extraction:
        - Try json.loads first (strict, fast).
        - On failure try json_repair (handles missing commas, trailing commas,
          truncated JSON — common LLM output defects).
        - Validate the parsed dict with the process Pydantic schema.
        - On ValidationError return the raw parsed dict so partial data is
          preserved rather than discarding the whole response.

        Returns None only when no JSON object can be found at all.
        """
        from json_repair import repair_json  # lazy import — not needed on the hot path

        content = raw_content.strip()

        # 1 & 2 — strip markdown code fences (greedy .* to capture full object)
        fence_match = re.search(
            r"```(?:json)?\s*(\{.*\})\s*```", content, re.DOTALL
        )
        if fence_match:
            content = fence_match.group(1)
        else:
            # 3 — outermost { ... }
            brace_match = re.search(r"\{.*\}", content, re.DOTALL)
            if brace_match:
                content = brace_match.group()
            else:
                step_warn(
                    "StructuredExtraction",
                    "No JSON object found in LLM response",
                )
                return None

        # Strict parse first
        try:
            data: Dict[str, Any] = json.loads(content)
        except json.JSONDecodeError as strict_exc:
            step_warn(
                "StructuredExtraction",
                f"json.loads failed ({strict_exc}) — attempting json_repair",
            )
            try:
                repaired = repair_json(content, return_objects=True)
                if not isinstance(repaired, dict):
                    step_warn(
                        "StructuredExtraction",
                        f"json_repair returned {type(repaired).__name__}, expected dict",
                    )
                    return None
                data = repaired
                step_warn("StructuredExtraction", "json_repair succeeded")
            except Exception as repair_exc:
                step_warn(
                    "StructuredExtraction",
                    f"json_repair also failed: {repair_exc}",
                )
                return None

        try:
            validated = process.output_schema.model_validate(data)
            return validated.model_dump()
        except ValidationError as exc:
            # Schema mismatch — return the raw parsed dict so partial data
            # is surfaced rather than discarding the entire response.
            step_warn(
                "StructuredExtraction",
                f"Pydantic validation error (returning raw dict): {exc}",
            )
            return data if isinstance(data, dict) else None

    @staticmethod
    def _truncate_document(parsed_document: Dict[str, Any]) -> tuple[Dict[str, Any], int]:
        """Return a copy of parsed_document limited to _MAX_PAGES pages."""
        pages = parsed_document.get("pages", [])
        truncated_pages = pages[:_MAX_PAGES]
        return (
            {"pages": truncated_pages, "page_count": len(truncated_pages)},
            len(truncated_pages),
        )

    def _load_prompt(self, process: OCRProcess) -> str:
        prompt_path = process.prompt_path
        if not prompt_path.exists():
            raise FileNotFoundError(
                f"Extraction prompt not found at {prompt_path} "
                f"for process_type={process.process_type!r}"
            )
        return prompt_path.read_text(encoding="utf-8").strip()

    @staticmethod
    def _compact_document(parsed_document: Dict[str, Any]) -> Dict[str, Any]:
        """Strip empty sections from each page to reduce payload size."""
        compact_pages = []
        for page in parsed_document.get("pages", []):
            compact: Dict[str, Any] = {"page": page["page"]}
            if page.get("lines"):
                compact["lines"] = page["lines"]
            if page.get("tables"):
                compact["tables"] = page["tables"]
            if page.get("selections"):
                compact["selections"] = page["selections"]
            if page.get("signatures"):
                compact["signatures"] = page["signatures"]
            compact_pages.append(compact)
        return {"pages": compact_pages, "page_count": len(compact_pages)}

    @staticmethod
    def _build_user_message(parsed_document: Dict[str, Any]) -> str:
        compact = StructuredExtractionNode._compact_document(parsed_document)
        # Use compact JSON (no whitespace) to reduce gateway payload size.
        payload = json.dumps(compact, ensure_ascii=False, separators=(",", ":"))
        return (
            "Here is the normalized OCR document extracted from the account opening form.\n\n"
            "```json\n"
            + payload
            + "\n```\n\n"
            "Extract all fields as specified in the system prompt."
        )

    @staticmethod
    def _empty_result(
        state: Dict[str, Any],
        t: Any,
        process: OCRProcess,
        error: str,
    ) -> Dict[str, Any]:
        """Return a schema-valid empty extraction when the LLM call fails.

        Instantiates the process output schema with all defaults (all-null fields)
        so downstream nodes always receive a properly-shaped dict rather than {}.
        The error is preserved in metadata; success is NOT set to False so the
        pipeline still returns a usable structured response.
        """
        try:
            empty_data: Dict[str, Any] = process.output_schema().model_dump()
        except Exception:
            empty_data = {}

        return {
            "extracted_data": empty_data,
            "status": "extracted",
            "metadata": {
                **state.get("metadata", {}),
                "extraction_complete": False,
                "extraction_error": error,
            },
        }

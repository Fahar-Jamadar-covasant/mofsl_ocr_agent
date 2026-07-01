"""
StructuredExtraction — extracts typed fields from the parsed OCR document using an LLM.
"""

import json
import re
from typing import Any, Dict

from langchain_core.messages import HumanMessage, SystemMessage

from cams_otel_lib import otel_trace
from src.config.agent_config import get_node_configuration
from src.utils.llm_provider import get_llm_model, get_provider_from_model
from src.ocr.process.base import OCRProcess
from src.ocr.process.factory import OCRProcessFactory
from src.ocr.storage.storage_service import StorageService
from src.ocr.utils.ocr_logger import step_start, step_done, step_error, step_warn


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

    @otel_trace
    async def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        process_type: str = state.get("process_type", "")
        process = OCRProcessFactory.resolve(process_type)

        parsed_document: Dict[str, Any] = state.get("parsed_document") or {}
        page_count = parsed_document.get("page_count", 0)

        t = step_start(
            "StructuredExtraction",
            process_type=process.process_type,
            pages=page_count,
            model=self.model,
            provider=str(self.provider),
        )

        system_prompt = self._load_prompt(process)
        user_message = self._build_user_message(parsed_document)

        custom_headers = state.get("litellm_headers")
        llm = get_llm_model(
            provider=self.provider,
            model_name=self.model,
            temperature=self.temperature,
            streaming=False,
            max_tokens=self.max_tokens,
            custom_headers=custom_headers,
        )
        # Call the LLM directly — Gemini via LiteLLM returns markdown-fenced JSON
        # which breaks the OpenAI SDK's strict model_validate_json() used internally
        # by with_structured_output. We strip the fence and validate with Pydantic
        # ourselves, achieving the same result without the SDK parsing step.
        try:
            raw_response = await llm.ainvoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_message),
            ])
        except Exception as exc:
            import traceback
            step_error(
                "StructuredExtraction",
                f"LLM call failed\n"
                f"  model={self.model!r}  provider={self.provider!r}\n"
                f"  error_type={type(exc).__name__}\n"
                f"  error={exc}\n"
                f"  traceback:\n{traceback.format_exc()}",
                elapsed=t.elapsed(),
            )
            raise

        raw_content: str = raw_response.content

        # Persist raw LLM output before any parsing — non-fatal if it fails
        document: str = state.get("document", "document")
        llm_output_path: str | None = None
        try:
            llm_output_path = await StorageService().save_llm_output(
                llm_output=raw_content,
                process_type=process_type,
                document_name=document,
            )
        except Exception as save_exc:
            step_warn("StructuredExtraction", f"failed to save LLM output — {save_exc}")

        # Strip markdown code fences (```json ... ``` or ``` ... ```)
        fenced = re.match(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", raw_content, re.DOTALL)
        json_str = fenced.group(1) if fenced else raw_content.strip()

        # Fall back to extracting the first JSON object if no fence was found
        if not fenced:
            json_match = re.search(r"\{.*\}", json_str, re.DOTALL)
            if json_match:
                json_str = json_match.group()

        try:
            parsed_obj = process.output_schema.model_validate_json(json_str)
            extracted_data: Dict[str, Any] = parsed_obj.model_dump()
        except Exception as val_exc:
            step_error(
                "StructuredExtraction",
                f"Pydantic validation failed\n"
                f"  error={val_exc}\n"
                f"  raw_content_preview={raw_content[:1000]!r}",
                elapsed=t.elapsed(),
            )
            raise

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
                "llm_output_path": llm_output_path,
            },
        }

    def _load_prompt(self, process: OCRProcess) -> str:
        prompt_path = process.prompt_path
        if not prompt_path.exists():
            raise FileNotFoundError(
                f"Extraction prompt not found at {prompt_path} "
                f"for process_type={process.process_type!r}"
            )
        return prompt_path.read_text(encoding="utf-8").strip()

    @staticmethod
    def _build_user_message(parsed_document: Dict[str, Any]) -> str:
        return (
            "Here is the normalized OCR document extracted from the account opening form.\n\n"
            "```json\n"
            + json.dumps(parsed_document, ensure_ascii=False, indent=2)
            + "\n```\n\n"
            "Extract all fields as specified in the system prompt."
        )

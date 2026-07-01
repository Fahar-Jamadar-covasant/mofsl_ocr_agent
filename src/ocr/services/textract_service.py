"""
Textract Service — submits documents to Amazon Textract and retrieves results.

Sources:
- `Amazon Textract/src/textract_service.py` — start_document_analysis,
  wait_for_completion, get_analysis_result.
- `Amazon Textract/main.py` — _merge_blocks (moved here where it belongs).

Changes from the originals:
- Wrapped in a class so the boto3 client is created once per instance.
- `wait_for_completion` polling loop converted from `time.sleep` to
  `asyncio.sleep` — the polling logic is otherwise unchanged.
- `get_analysis_result` pagination wrapped in `asyncio.to_thread` — the
  pagination logic is otherwise unchanged.
- `_merge_blocks` moved from main.py into this service and made public as
  `merge_blocks`.
- `print()` replaced by the project logger.
- Configuration resolved from `settings` instead of a standalone config module.
- High-level `analyze_document` method orchestrates the full pipeline so nodes
  only need one call.

Business logic is otherwise identical to the originals.
"""

import asyncio
import os
from typing import Any, Dict, List, Optional, Tuple

import boto3

from cams_otel_lib import Logger as logger, otel_trace
from src.config.settings import settings

# Textract feature types requested — identical to the original config
_FEATURE_TYPES = ["FORMS", "TABLES", "LAYOUT", "SIGNATURES"]

# Polling interval (seconds) — matches original `time.sleep(5)`
_POLL_INTERVAL_SECONDS = 5


class TextractService:
    """
    Encapsulates all Amazon Textract interactions required by the OCR pipeline.

    The boto3 client is instantiated once in __init__ and reused for every
    call, matching the module-level client pattern of the original code.
    """

    @otel_trace
    def __init__(
        self,
        bucket_name: Optional[str] = None,
        region_name: Optional[str] = None,
    ) -> None:
        self.bucket_name: str = (
            bucket_name
            or settings.s3_bucket_name
            or os.getenv("S3_BUCKET_NAME", "")
        )
        self.region_name: str = (
            region_name
            or settings.aws_region
            or os.getenv("AWS_REGION", "")
        )

        client_kwargs: dict = {"service_name": "textract"}
        if self.region_name:
            client_kwargs["region_name"] = self.region_name
        if settings.aws_access_key_id:
            client_kwargs["aws_access_key_id"] = settings.aws_access_key_id
        if settings.aws_secret_access_key:
            client_kwargs["aws_secret_access_key"] = settings.aws_secret_access_key

        self._client = boto3.client(**client_kwargs)

        logger.debug(
            f"TextractService initialised — bucket={self.bucket_name!r}, "
            f"region={self.region_name!r}"
        )

    # ──────────────────────────────────────────────────────────────────────────
    # High-level async API (called by RunTextractNode)
    # ──────────────────────────────────────────────────────────────────────────

    @otel_trace
    async def analyze_document(
        self, s3_object_key: str
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Full Textract pipeline for one document.

        Orchestrates:
        1. start_document_analysis — submits the job
        2. wait_for_completion    — polls until SUCCEEDED or FAILED
        3. get_analysis_result    — paginates through all result pages
        4. merge_blocks           — flattens all page blocks into one list

        Args:
            s3_object_key: S3 key of the document to analyse.

        Returns:
            Tuple of (job_id, merged_response) where merged_response is:
            {
                "Blocks": [ ... all blocks from all pages ... ],
                "JobStatus": "SUCCEEDED",
                "DocumentMetadata": { ... from the first page ... }
            }
        """
        logger.info(
            f"Starting Textract analysis — "
            f"bucket={self.bucket_name!r}, key={s3_object_key!r}"
        )

        job_id = await self._start_document_analysis(s3_object_key)
        logger.info(f"Textract job submitted — job_id={job_id!r}")

        await self._wait_for_completion(job_id)
        logger.info(f"Textract job completed — job_id={job_id!r}")

        raw_pages = await self._get_analysis_result(job_id)
        logger.info(
            f"Textract pages retrieved — "
            f"job_id={job_id!r}, pages={len(raw_pages)}"
        )

        merged_response = self._build_merged_response(raw_pages)
        logger.info(
            f"Textract blocks merged — "
            f"job_id={job_id!r}, total_blocks={len(merged_response['Blocks'])}"
        )

        return job_id, merged_response

    # ──────────────────────────────────────────────────────────────────────────
    # Block merging (moved from Amazon Textract/main.py)
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def merge_blocks(raw_pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Flatten blocks from all paginated Textract responses into one list.

        Identical to _merge_blocks() in Amazon Textract/main.py — moved here
        because it is a Textract concern, not an orchestration concern.

        Args:
            raw_pages: List of raw page responses from get_analysis_result.

        Returns:
            Flat list of all Textract Block dicts.
        """
        all_blocks: List[Dict[str, Any]] = []
        for page in raw_pages:
            all_blocks.extend(page.get("Blocks", []))
        return all_blocks

    # ──────────────────────────────────────────────────────────────────────────
    # Private async helpers
    # ──────────────────────────────────────────────────────────────────────────

    @otel_trace
    async def _start_document_analysis(self, document_name: str) -> str:
        """
        Starts asynchronous Textract analysis.

        Identical to start_document_analysis() in the original textract_service.py
        except the boto3 call is wrapped in asyncio.to_thread.
        """
        def _sync() -> str:
            response = self._client.start_document_analysis(
                DocumentLocation={
                    "S3Object": {
                        "Bucket": self.bucket_name,
                        "Name": document_name,
                    }
                },
                FeatureTypes=_FEATURE_TYPES,
            )
            return response["JobId"]

        return await asyncio.to_thread(_sync)

    @otel_trace
    async def _wait_for_completion(self, job_id: str) -> None:
        """
        Polls Textract until the job succeeds or fails.

        Identical logic to wait_for_completion() in the original
        textract_service.py — `time.sleep(5)` replaced by `asyncio.sleep(5)`
        so the event loop is not blocked during polling.
        """
        while True:
            response = await asyncio.to_thread(
                self._client.get_document_analysis,
                JobId=job_id,
            )

            status = response["JobStatus"]
            logger.info(f"Textract job status — job_id={job_id!r}, status={status!r}")

            if status == "SUCCEEDED":
                return

            if status == "FAILED":
                raise RuntimeError(f"Textract job failed — job_id={job_id!r}")

            await asyncio.sleep(_POLL_INTERVAL_SECONDS)

    @otel_trace
    async def _get_analysis_result(self, job_id: str) -> List[Dict[str, Any]]:
        """
        Retrieves all paginated Textract result pages.

        Identical logic to get_analysis_result() in the original
        textract_service.py — boto3 calls wrapped in asyncio.to_thread.
        """
        pages: List[Dict[str, Any]] = []
        next_token: Optional[str] = None

        while True:
            kwargs: dict = {"JobId": job_id}
            if next_token:
                kwargs["NextToken"] = next_token

            response = await asyncio.to_thread(
                self._client.get_document_analysis,
                **kwargs,
            )

            pages.append(response)
            next_token = response.get("NextToken")

            if not next_token:
                break

        return pages

    # ──────────────────────────────────────────────────────────────────────────
    # Private helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _build_merged_response(
        self, raw_pages: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Build a single merged Textract response from all paginated pages.

        The merged structure is what TextractParser expects in Phase 4:
            { "Blocks": [ ... all blocks ... ], "JobStatus": "SUCCEEDED", ... }
        """
        all_blocks = self.merge_blocks(raw_pages)

        # Carry metadata from the first page for traceability
        first_page = raw_pages[0] if raw_pages else {}

        return {
            "Blocks": all_blocks,
            "JobStatus": first_page.get("JobStatus", "SUCCEEDED"),
            "DocumentMetadata": first_page.get("DocumentMetadata", {}),
        }

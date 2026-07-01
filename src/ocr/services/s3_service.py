"""
S3 Service — uploads documents to Amazon S3 before Textract processing.

Source: adapted from `Amazon Textract/src/s3_service.py`.

Changes from the original:
- Wrapped in a class so the boto3 client is created once per service instance.
- `upload_pdf` is now `async` via `asyncio.to_thread` — the boto3 call itself
  is unchanged; only the execution context differs.
- `print()` replaced by the project logger.
- Bucket name and region resolved from `settings` instead of a standalone
  config module.

Business logic is otherwise identical to the original.
"""

import asyncio
import os
from typing import Optional

import boto3

from cams_otel_lib import Logger as logger, otel_trace
from src.config.settings import settings


class S3Service:
    """
    Encapsulates all S3 interactions required by the OCR pipeline.

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

        # Build boto3 client kwargs — only pass credentials when explicitly set
        # so IAM roles / instance profiles continue to work without config.
        client_kwargs: dict = {"service_name": "s3"}
        if self.region_name:
            client_kwargs["region_name"] = self.region_name
        if settings.aws_access_key_id:
            client_kwargs["aws_access_key_id"] = settings.aws_access_key_id
        if settings.aws_secret_access_key:
            client_kwargs["aws_secret_access_key"] = settings.aws_secret_access_key

        self._client = boto3.client(**client_kwargs)

        logger.debug(
            f"S3Service initialised — bucket={self.bucket_name!r}, "
            f"region={self.region_name!r}"
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Public async API
    # ──────────────────────────────────────────────────────────────────────────

    @otel_trace
    async def upload_document(self, file_path: str) -> str:
        """
        Upload a local file to S3 and return the S3 object key.

        Preserves the original `upload_pdf` logic exactly:
        - The object key is the basename of the local file path.
        - The file is uploaded to the configured bucket.

        Args:
            file_path: Absolute or relative path to the local file.

        Returns:
            S3 object key (basename of the uploaded file).
        """
        object_key = os.path.basename(file_path)

        logger.info(f"Uploading {object_key!r} to S3 bucket {self.bucket_name!r} ...")

        await asyncio.to_thread(
            self._upload_file_sync,
            file_path,
            object_key,
        )

        logger.info(f"S3 upload successful — object_key={object_key!r}")
        return object_key

    # ──────────────────────────────────────────────────────────────────────────
    # Private sync helpers (run inside asyncio.to_thread)
    # ──────────────────────────────────────────────────────────────────────────

    def _upload_file_sync(self, file_path: str, object_key: str) -> None:
        """Synchronous boto3 upload — identical to the original upload_pdf body."""
        self._client.upload_file(
            Filename=file_path,
            Bucket=self.bucket_name,
            Key=object_key,
        )

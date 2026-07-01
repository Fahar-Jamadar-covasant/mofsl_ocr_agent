"""
StorageService — writes extracted_data to the local filesystem as JSON.

Responsibilities:
- Resolve and create the output directory.
- Write the JSON file atomically (temp file → rename).
- Return the absolute path of the saved file.

No database operations are performed here.
"""

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict

from cams_otel_lib import Logger as logger, otel_trace

# Base output directory — overridable via OCR_OUTPUT_DIR environment variable
_DEFAULT_OUTPUT_DIR = Path("/tmp/ocr-output")


class StorageService:

    @otel_trace
    def __init__(self, base_dir: Path | None = None) -> None:
        env_override = os.environ.get("OCR_OUTPUT_DIR")
        self.base_dir = Path(env_override) if env_override else (base_dir or _DEFAULT_OUTPUT_DIR)

    @otel_trace
    async def save_extracted_data(
        self,
        extracted_data: Dict[str, Any],
        process_type: str,
        document_name: str,
    ) -> str:
        """
        Persist extracted_data as a JSON file and return the absolute file path.

        Directory structure:
            <base_dir>/<process_type>/<document_name>.json

        The write is atomic: data is written to a temp file in the same directory
        and then renamed to the final path so readers never see a partial file.

        Args:
            extracted_data:  Validated extraction result dict.
            process_type:    e.g. "individual_account_opening".
            document_name:   Used as the filename stem (basename of the source path).

        Returns:
            Absolute path of the saved JSON file as a string.
        """
        output_dir = self.base_dir / process_type
        output_dir.mkdir(parents=True, exist_ok=True)

        # Use the basename so "/path/to/form.pdf" → "form.pdf.json"
        stem = Path(document_name).name
        final_path = output_dir / f"{stem}.json"

        # Atomic write: temp file in the same directory to ensure same filesystem
        tmp_fd, tmp_path = tempfile.mkstemp(dir=output_dir, suffix=".tmp")
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
                json.dump(extracted_data, fh, ensure_ascii=False, indent=2)
            os.replace(tmp_path, final_path)
        except Exception:
            # Clean up the temp file on failure
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

        logger.info(
            f"StorageService saved extracted data — path={str(final_path)!r}, "
            f"process_type={process_type!r}"
        )
        return str(final_path)

    @otel_trace
    async def save_parsed_document(
        self,
        parsed_document: Dict[str, Any],
        process_type: str,
        document_name: str,
    ) -> str:
        """
        Persist the parsed document (as sent to the LLM) for inspection.

        Directory structure:
            <base_dir>/<process_type>/parsed/<document_name>.json

        Returns:
            Absolute path of the saved JSON file as a string.
        """
        output_dir = self.base_dir / process_type / "parsed"
        output_dir.mkdir(parents=True, exist_ok=True)

        stem = Path(document_name).name
        final_path = output_dir / f"{stem}.json"

        tmp_fd, tmp_path = tempfile.mkstemp(dir=output_dir, suffix=".tmp")
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
                json.dump(parsed_document, fh, ensure_ascii=False, indent=2)
            os.replace(tmp_path, final_path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

        logger.info(
            f"StorageService saved parsed document — path={str(final_path)!r}, "
            f"process_type={process_type!r}"
        )
        return str(final_path)

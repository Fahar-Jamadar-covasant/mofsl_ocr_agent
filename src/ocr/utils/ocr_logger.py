"""
OCR pipeline terminal + file logger.

Every OCR run is printed to the terminal AND appended to a rotating log file.

Log file location (in order of priority):
  1. OCR_LOG_DIR environment variable
  2. OCR_OUTPUT_DIR/logs/  (next to the extracted JSON output)
  3. ./logs/ocr_pipeline.log  (fallback)

A new log file is started each day: ocr_pipeline_YYYY-MM-DD.log
"""

import logging
import logging.handlers
import os
import sys
import time
from datetime import datetime
from pathlib import Path


# ── Resolve log directory ─────────────────────────────────────────────────────

def _resolve_log_dir() -> Path:
    log_dir = os.environ.get("OCR_LOG_DIR")
    if log_dir:
        return Path(log_dir)
    output_dir = os.environ.get("OCR_OUTPUT_DIR")
    if output_dir:
        return Path(output_dir) / "logs"
    return Path("logs")


_LOG_DIR = _resolve_log_dir()
_LOG_DIR.mkdir(parents=True, exist_ok=True)
_LOG_FILE = _LOG_DIR / "ocr_pipeline.log"

_FMT = logging.Formatter(
    fmt="%(asctime)s  [OCR] %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# ── Build the logger (once) ───────────────────────────────────────────────────

_logger = logging.getLogger("ocr_pipeline")

if not _logger.handlers:
    # Terminal handler
    _console = logging.StreamHandler(sys.stdout)
    _console.setFormatter(_FMT)
    _logger.addHandler(_console)

    # File handler — rotates at midnight, keeps 30 days of logs
    _file = logging.handlers.TimedRotatingFileHandler(
        filename=str(_LOG_FILE),
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
    )
    _file.setFormatter(_FMT)
    _logger.addHandler(_file)

    _logger.setLevel(logging.DEBUG)
    _logger.propagate = False

    _logger.info(f"OCR log file: {_LOG_FILE.resolve()}")


# ── Timer ─────────────────────────────────────────────────────────────────────

class _Timer:
    def __init__(self) -> None:
        self._start = time.perf_counter()
        self.started_at = datetime.now().strftime("%H:%M:%S")

    def elapsed(self) -> str:
        ms = (time.perf_counter() - self._start) * 1000
        return f"{ms:.0f}ms" if ms < 1000 else f"{ms / 1000:.2f}s"


# ── Public API ────────────────────────────────────────────────────────────────

def step_start(node: str, **kwargs) -> _Timer:
    parts = "  ".join(f"{k}={v!r}" for k, v in kwargs.items())
    _logger.info(f"▶  {node:<30}  START   {parts}")
    return _Timer()


def step_done(node: str, elapsed: str = "", **kwargs) -> None:
    parts = "  ".join(f"{k}={v!r}" for k, v in kwargs.items())
    time_str = f"  [{elapsed}]" if elapsed else ""
    _logger.info(f"✔  {node:<30}  DONE {time_str}  {parts}")


def step_error(node: str, error: str, elapsed: str = "") -> None:
    time_str = f"  [{elapsed}]" if elapsed else ""
    _logger.error(f"✘  {node:<30}  ERROR{time_str}  error={error!r}")


def step_warn(node: str, message: str) -> None:
    _logger.warning(f"⚠  {node:<30}  WARN    {message}")


def pipeline_start(document: str, process_type: str) -> _Timer:
    _logger.info("=" * 70)
    _logger.info("  OCR PIPELINE START")
    _logger.info(f"  document     : {document}")
    _logger.info(f"  process_type : {process_type}")
    _logger.info("=" * 70)
    return _Timer()


def pipeline_done(success: bool, elapsed: str, parsed_json_path: str = "") -> None:
    status = "SUCCESS" if success else "FAILED"
    _logger.info("=" * 70)
    _logger.info(f"  OCR PIPELINE {status}   total_time={elapsed}")
    if parsed_json_path:
        _logger.info(f"  output       : {parsed_json_path}")
    _logger.info("=" * 70)

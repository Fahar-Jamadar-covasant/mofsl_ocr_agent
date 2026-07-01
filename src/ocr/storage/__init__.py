"""
OCR storage layer — local file and database persistence.
"""

from .database import Base, create_tables, get_engine, get_session, get_session_factory
from .storage_service import StorageService

__all__ = [
    "Base",
    "create_tables",
    "get_engine",
    "get_session",
    "get_session_factory",
    "StorageService",
]

"""
Ingestion package for VaultRAG.
"""

from app.ingestion.pipeline import (
    ingest_corpus,
    ingest_document,
    ingest_folder,
    ingest_pdf,
)

__all__ = [
    "ingest_pdf",
    "ingest_folder",
    "ingest_document",
    "ingest_corpus",
]

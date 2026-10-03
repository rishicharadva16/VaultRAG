"""
Ingestion package for VaultRAG.
"""

from app.ingestion.pipeline import ingest_pdf, ingest_folder
from app.ingestion.manifest import load_manifest, resolve_manifest

__all__ = ["ingest_pdf", "ingest_folder", "load_manifest", "resolve_manifest"]

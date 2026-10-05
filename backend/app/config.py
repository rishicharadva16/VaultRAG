from pathlib import Path

from pydantic_settings import BaseSettings

# .env lives in the repo root (parent of backend/)
_repo_root = Path(__file__).resolve().parent.parent.parent
_env_file = _repo_root / ".env"


class Settings(BaseSettings):
    # PostgreSQL
    DATABASE_URL: str = "postgresql://vaultrag:changeme@localhost:5432/vaultrag"

    # Qdrant
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_COLLECTION: str = "vaultrag_chunks"
    QDRANT_TEST_COLLECTION: str = "vaultrag_test_chunks"

    # JWT
    JWT_SECRET: str = "CHANGE_ME"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 30

    # Ollama
    OLLAMA_URL: str = "http://localhost:11434"

    # CORS – comma-separated origins, no wildcards, no "null"
    CORS_ORIGINS: str = (
        "http://localhost:3000,http://127.0.0.1:3000,"
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:8080,http://127.0.0.1:8080"
    )

    # Embeddings (Step 2)
    EMBED_MODEL: str = "BAAI/bge-m3"
    SPARSE_MODEL: str = "Qdrant/bm25"

    # Search & Reranking (Step 3)
    ALLOW_SELF_REGISTER: bool = False
    RERANK_ENABLED: bool = False
    RERANK_CANDIDATES: int = 20
    RERANK_MODEL: str = "BAAI/bge-reranker-v2-m3"
    SEARCH_RATE_LIMIT_PER_MINUTE: int = 60

    # Dataset path (relative to repo root)
    DATASET_DIR: str = "data/northwind/rag_demo_dataset"

    model_config = {
        "env_file": str(_env_file) if _env_file.exists() else ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    def cors_origin_list(self) -> list[str]:
        """Parse CORS_ORIGINS into a list, filtering out empty and 'null'."""
        return [
            o.strip() for o in self.CORS_ORIGINS.split(",")
            if o.strip() and o.strip().lower() != "null"
        ]

    def dataset_path(self) -> Path:
        """Resolve DATASET_DIR relative to repository root."""
        return (_repo_root / self.DATASET_DIR).resolve()


settings = Settings()

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
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080,http://127.0.0.1:8080"

    # Embeddings (Step 2)
    EMBED_MODEL: str = "BAAI/bge-m3"
    SPARSE_MODEL: str = "Qdrant/bm25"

    # Search & Reranking (Step 3)
    ALLOW_SELF_REGISTER: bool = False
    RERANK_ENABLED: bool = False
    RERANK_CANDIDATES: int = 20
    RERANK_MODEL: str = "BAAI/bge-reranker-v2-m3"
    SEARCH_RATE_LIMIT_PER_MINUTE: int = 60

    # LLM & Generation (Step 5)
    LLM_PROVIDER: str = "ollama"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    LLM_MODEL: str = "qwen2.5:7b"
    LLM_FALLBACK_MODEL: str = "qwen2.5:3b"
    LLM_FALLBACK_ENABLED: bool = False
    LLM_TIMEOUT_S: int = 90
    LLM_MAX_TOKENS: int = 512
    LLM_TEMPERATURE: float = 0.0

    # Ask, Citations & Thresholds (Step 5)
    ASK_TOP_K: int = 5
    ASK_CANDIDATES: int = 10
    ASK_USE_RERANK: bool = True
    ASK_MIN_CONFIDENCE: float = 0.40
    RELEVANCE_THRESHOLD: float = 0.05
    SUPPORT_THRESHOLD: float = 0.05
    VERIFY_WITH_LLM: bool = False
    ASK_RATE_LIMIT_PER_MINUTE: int = 20


    # Access Model (Step 5e: department | dataset)
    ACCESS_MODEL: str = "department"
    POLICIES_COMPANY_WIDE: bool = True

    # Demo Visible Users (comma-separated emails or IDs)
    DEMO_VISIBLE_USERS: str = "admin@northwind.example,meera.iyer@northwind.example,karan.shah@northwind.example,asha.patel@northwind.example,u_admin,u_meera,u_karan,u_asha"

    # Admin Access
    # When true, role:admin is added to the ACL of every chunk so the platform admin can read all documents. All admin reads are audited.
    ADMIN_SEES_ALL: bool = True

    # OCR & Image Ingestion (Step 4b)
    OCR_ENGINE: str = "rapidocr"
    OCR_MIN_CONFIDENCE: float = 0.5

    # Dataset path (relative to repo root)
    DATASET_DIR: str = "data/northwind/rag_demo_dataset"

    # Live Upload & Sharing (Step 6)
    UPLOAD_ROLES: str = "employee,manager,hr_admin,finance_admin,admin"
    MAX_UPLOAD_MB: int = 20
    UPLOADS_PER_HOUR: int = 20
    STORAGE_DIR: str = str(_repo_root / "storage")

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

    def storage_path(self) -> Path:
        """Resolve STORAGE_DIR to absolute path."""
        p = Path(self.STORAGE_DIR)
        if not p.is_absolute():
            return (_repo_root / p).resolve()
        return p.resolve()

    def upload_role_list(self) -> list[str]:
        """List of roles permitted to upload files."""
        return [r.strip() for r in self.UPLOAD_ROLES.split(",") if r.strip()]


settings = Settings()

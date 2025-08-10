import os
from dataclasses import dataclass


@dataclass
class Settings:
    database_url: str
    storage_dir: str = "./data/pdfs"
    arxiv_max_results: int = 10
    rate_limit_delay_seconds: int = 3
    request_timeout_seconds: int = 30
    # Ranking/semantic config
    enable_semantic: bool = False
    semantic_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    weight_semantic: float = 1.0
    weight_citations: float = 0.2
    weight_recency: float = 0.1
    semantic_topk: int = 50
    # Parser
    parser_backend: str = "pdfminer"  # pdfminer|grobid
    grobid_host: str = "http://localhost:8070"

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            database_url=os.environ.get("DATABASE_URL", "sqlite:///./data/literature.db"),
            storage_dir=os.environ.get("STORAGE_DIR", "./data/pdfs"),
            arxiv_max_results=int(os.environ.get("ARXIV_MAX_RESULTS", "10")),
            rate_limit_delay_seconds=int(os.environ.get("RATE_LIMIT_DELAY_SECONDS", "3")),
            request_timeout_seconds=int(os.environ.get("REQUEST_TIMEOUT_SECONDS", "30")),
            enable_semantic=os.environ.get("ENABLE_SEMANTIC", "0") == "1",
            semantic_model=os.environ.get(
                "SEMANTIC_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
            ),
            weight_semantic=float(os.environ.get("WEIGHT_SEMANTIC", "1.0")),
            weight_citations=float(os.environ.get("WEIGHT_CITATIONS", "0.2")),
            weight_recency=float(os.environ.get("WEIGHT_RECENCY", "0.1")),
            semantic_topk=int(os.environ.get("SEMANTIC_TOPK", "50")),
            parser_backend=os.environ.get("PARSER_BACKEND", "pdfminer"),
            grobid_host=os.environ.get("GROBID_HOST", "http://localhost:8070"),
        )

import os
from dataclasses import dataclass


@dataclass
class Settings:
    database_url: str
    storage_dir: str = "./data/pdfs"
    arxiv_max_results: int = 10
    rate_limit_delay_seconds: int = 3
    request_timeout_seconds: int = 30

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            database_url=os.environ.get("DATABASE_URL", "sqlite:///./data/literature.db"),
            storage_dir=os.environ.get("STORAGE_DIR", "./data/pdfs"),
            arxiv_max_results=int(os.environ.get("ARXIV_MAX_RESULTS", "10")),
            rate_limit_delay_seconds=int(os.environ.get("RATE_LIMIT_DELAY_SECONDS", "3")),
            request_timeout_seconds=int(os.environ.get("REQUEST_TIMEOUT_SECONDS", "30")),
        )

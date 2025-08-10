from __future__ import annotations

import hashlib
import re
from pathlib import Path

import requests
from tenacity import retry, stop_after_attempt, wait_exponential


def ensure_storage_dir(storage_dir: str) -> Path:
    path = Path(storage_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _hash_string(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _sanitize_file_name(file_name: str) -> str:
    """Replace path separators and invalid characters with underscores.

    Allows alphanumerics, dash, underscore, and dot.
    """
    # Normalize path separators first
    file_name = file_name.replace("\\", "/")
    file_name = file_name.split("/")[-1]
    return re.sub(r"[^A-Za-z0-9._-]", "_", file_name)


@retry(wait=wait_exponential(min=1, max=10), stop=stop_after_attempt(3))
def download_pdf_to_storage(
    pdf_url: str,
    storage_dir: str,
    file_hint: str | None = None,
    timeout_seconds: int = 30,
) -> str:
    ensure_storage_dir(storage_dir)
    file_name = file_hint or _hash_string(pdf_url)
    if not file_name.endswith(".pdf"):
        file_name = f"{file_name}.pdf"
    file_name = _sanitize_file_name(file_name)
    dest = Path(storage_dir) / file_name
    # Ensure any intermediate directories exist (in case hint contained separators previously)
    dest.parent.mkdir(parents=True, exist_ok=True)

    with requests.get(pdf_url, stream=True, timeout=timeout_seconds) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

    return str(dest)

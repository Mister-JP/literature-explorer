from __future__ import annotations

import hashlib

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Paper


def _normalize(s: str | None) -> str:
    return (s or "").strip().lower()


def _hash_identity(title: str, authors: list[str]) -> str:
    payload = f"{_normalize(title)}|{'|'.join(sorted(_normalize(a) for a in authors))}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def is_duplicate(
    session: Session,
    source: str,
    doi: str | None,
    external_id: str | None,
    title: str | None = None,
    authors: list[str] | None = None,
) -> bool:
    # Prefer DOI if present
    if doi:
        stmt = select(Paper.id).where(Paper.doi == doi)
        if session.execute(stmt).scalar_one_or_none() is not None:
            return True

    # Then use source + external_id
    if external_id:
        stmt = select(Paper.id).where(Paper.source == source, Paper.external_id == external_id)
        if session.execute(stmt).scalar_one_or_none() is not None:
            return True

    # Finally, heuristic by title/authors hash
    if title and authors:
        identity_hash = _hash_identity(title, authors)
        # A lightweight scan; in real systems, store this hash in DB column with an index
        stmt = select(Paper.id, Paper.title, Paper.authors)
        for _id, existing_title, existing_authors in session.execute(stmt):
            existing_hash = _hash_identity(existing_title, existing_authors.get("list", []))
            if existing_hash == identity_hash:
                return True

    return False

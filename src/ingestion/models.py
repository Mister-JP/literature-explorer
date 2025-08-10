from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON as GenericJSON
from sqlalchemy import DateTime, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class Paper(Base):
    __tablename__ = "papers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g., "arxiv"
    external_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    doi: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    title: Mapped[str] = mapped_column(String(2048), nullable=False)
    authors: Mapped[dict] = mapped_column(
        JSONB().with_variant(GenericJSON(), "sqlite"), default=dict, nullable=False
    )  # {"list": ["Author A", ...]}
    abstract: Mapped[str | None] = mapped_column(String(10000), nullable=True)
    license: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pdf_path: Mapped[str | None] = mapped_column(String(4096), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now_utc)

    __table_args__ = (UniqueConstraint("source", "external_id", name="uq_source_external_id"),)

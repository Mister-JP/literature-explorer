from .arxiv import ArxivConnector
from .base import Connector, PaperMetadata, PDFRef, QuerySpec
from .openalex import OpenAlexConnector

__all__ = [
    "Connector",
    "PaperMetadata",
    "QuerySpec",
    "PDFRef",
    "ArxivConnector",
    "OpenAlexConnector",
]

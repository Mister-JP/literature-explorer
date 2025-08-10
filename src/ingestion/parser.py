from __future__ import annotations

import re


def _extract_text_pdfminer(pdf_path: str) -> str:
    """Extract text from a PDF using pdfminer.six. Imported lazily to avoid hard dep at import time."""
    try:
        from pdfminer.high_level import extract_text  # type: ignore
    except Exception as exc:  # pragma: no cover - optional dependency
        raise RuntimeError(
            "pdfminer.six is required for PDF parsing. Install it via requirements.txt."
        ) from exc
    return extract_text(pdf_path) or ""


SECTION_NAMES = [
    "Title",
    "Abstract",
    "Introduction",
    "Background",
    "Methods",
    "Method",
    "Materials and Methods",
    "Results",
    "Discussion",
    "Conclusion",
    "Conclusions",
    "References",
]


def split_text_into_sections(text: str) -> dict[str, str]:
    """Split raw text into sections using heuristic header detection.

    Pure function for unit-testing without touching PDF IO.
    """
    if not text:
        return {}

    text = re.sub(r"\r\n?", "\n", text)
    lines = [ln.strip() for ln in text.split("\n")]

    # Markers for headers (case-insensitive, standalone line)
    header_pattern = re.compile(
        r"^(abstract|introduction|background|methods?|materials and methods|results|discussion|conclusions?|references)\s*$",
        re.IGNORECASE,
    )

    sections: dict[str, str] = {}
    current_header = "Body"
    buffer: list[str] = []
    for ln in lines:
        if header_pattern.match(ln):
            # flush previous
            if buffer:
                sections[current_header] = (
                    sections.get(current_header, "") + "\n" + "\n".join(buffer)
                ).strip()
            # start new
            hdr = ln.strip().title()
            if hdr.lower().startswith("method"):
                hdr = "Methods"
            if hdr.lower().startswith("conclusion"):
                hdr = "Conclusion"
            current_header = hdr
            buffer = []
        else:
            buffer.append(ln)

    if buffer:
        sections[current_header] = (
            sections.get(current_header, "") + "\n" + "\n".join(buffer)
        ).strip()

    # Inject Title if missing by taking the first non-empty line from the document
    if "Title" not in sections:
        first_nonempty = next((ln for ln in lines if ln), "")
        if first_nonempty:
            sections["Title"] = first_nonempty

    # Keep only known sections + Title/Body
    cleaned: dict[str, str] = {}
    for key, val in sections.items():
        if (
            (key in {"Body", "Title"} or any(key.lower() == s.lower() for s in SECTION_NAMES))
            and val
            and val.strip()
        ):
            cleaned[key] = val.strip()
    return cleaned


def parse_pdf_into_sections(pdf_path: str) -> dict[str, str]:
    """Heuristic parser: extract text and segment by common section headers.

    Returns a dict keyed by canonical section names with raw text.
    """
    full_text = _extract_text_pdfminer(pdf_path)
    return split_text_into_sections(full_text)


def extract_abstract_and_conclusion(sections: dict[str, str]) -> tuple[str | None, str | None]:
    abstract = sections.get("Abstract")
    conclusion = sections.get("Conclusion") or sections.get("Conclusions")
    # Fallback for conclusion: last paragraph of Discussion
    if not conclusion and sections.get("Discussion"):
        paras = [p.strip() for p in sections["Discussion"].split("\n\n") if p.strip()]
        if paras:
            conclusion = paras[-1]
    return abstract, conclusion

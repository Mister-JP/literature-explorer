from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import requests

TEI_NS = {"tei": "http://www.tei-c.org/ns/1.0"}


def _text_or_empty(el) -> str:
    if el is None:
        return ""
    return " ".join(el.itertext())


def grobid_parse_pdf(pdf_path: str, host: str = "http://localhost:8070") -> dict[str, str]:
    """Send PDF to a running GROBID server and parse TEI to sections.

    Returns a mapping of section name to text. Best-effort; returns {} on failure.
    """
    try:
        url = host.rstrip("/") + "/api/processFulltextDocument"
        with open(Path(pdf_path), "rb") as f:
            files = {"input": (Path(pdf_path).name, f, "application/pdf")}
            resp = requests.post(url, files=files, timeout=60)
        resp.raise_for_status()
        tei_xml = resp.text or ""
        if not tei_xml.strip():
            return {}
        root = ET.fromstring(tei_xml)
        sections: dict[str, str] = {}
        # Title
        title_el = root.find(".//tei:titleStmt/tei:title", TEI_NS)
        if title_el is not None:
            sections["Title"] = _text_or_empty(title_el).strip()
        # Abstract
        abs_el = root.find(".//tei:abstract", TEI_NS)
        if abs_el is not None:
            sections["Abstract"] = _text_or_empty(abs_el).strip()
        # Body sections
        for div in root.findall(".//tei:body//tei:div", TEI_NS):
            head = div.find("tei:head", TEI_NS)
            name = _text_or_empty(head).strip() or (div.get("type") or "Section")
            # Normalize some common names
            low = name.lower()
            if low.startswith("method"):
                name = "Methods"
            elif low.startswith("conclusion"):
                name = "Conclusion"
            elif low.startswith("introduction"):
                name = "Introduction"
            elif low.startswith("discussion"):
                name = "Discussion"
            elif low.startswith("result"):
                name = "Results"
            # Collect paragraphs
            paras = [
                _text_or_empty(p).strip()
                for p in div.findall(".//tei:p", TEI_NS)
                if _text_or_empty(p).strip()
            ]
            if paras:
                text = "\n\n".join(paras)
                existing = sections.get(name, "")
                sections[name] = (existing + ("\n\n" if existing else "") + text).strip()
        return sections
    except Exception:
        return {}

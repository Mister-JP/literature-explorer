from __future__ import annotations

from ingestion.parser import extract_abstract_and_conclusion, split_text_into_sections
from ingestion.summarizer import ExtractiveSummarizer, extractive_summary, summarize_sections


def test_split_text_into_sections_basic():
    text = """
    A Great Title

    Abstract
    This paper introduces a method.

    Introduction
    Many works study X.

    Methods
    We propose Y.

    Results
    Our method outperforms baselines.

    Discussion
    We discuss implications.

    Conclusion
    We conclude with future work.
    """.strip()
    sections = split_text_into_sections(text)
    assert sections["Title"].startswith("A Great Title")
    assert "introduces a method" in sections.get("Abstract", "").lower()
    assert "We propose" in sections.get("Methods", "")


def test_split_text_empty_returns_empty_sections():
    sections = split_text_into_sections("")
    assert sections == {}


def test_extract_abstract_conclusion_with_fallback():
    sections = {
        "Title": "T",
        "Discussion": "Para1.\n\nPara2 is the end.",
    }
    abstract, conclusion = extract_abstract_and_conclusion(sections)
    assert abstract is None
    assert conclusion == "Para2 is the end."


def test_extractive_summary_limits():
    text = "One. Two. Three. Four. Five. Six."
    out = extractive_summary(text, max_sentences=3, max_chars=20)
    assert len(out) <= 20
    assert out.count(".") <= 3


def test_summarizer_service_with_abstract():
    svc = ExtractiveSummarizer(max_sentences=2, max_chars=200)
    out = svc.summarize(sections=None, abstract="Sentence one. Sentence two. Sentence three.")
    assert out and out.endswith(".")


def test_summarize_sections_prefers_methods_results_conclusion():
    sections = {
        "Introduction": "Intro text.",
        "Methods": "We used method A. Details follow.",
        "Results": "We found significant improvement.",
        "Discussion": "We discuss.",
        "Conclusion": "This work advances the field.",
    }
    out = summarize_sections(sections)
    # Expect the output to include content from Methods/Results/Conclusion preference order
    assert (
        "method" in out.lower() or "results" in out.lower() or "advances the field" in out.lower()
    )


def test_summarize_sections_caps_sentences_and_chars():
    sections = {
        "Abstract": "One. Two. Three. Four. Five. Six.",
        "Methods": "A. B. C. D.",
        "Results": "R1. R2. R3.",
        "Conclusion": "Good.",
    }
    out = summarize_sections(sections)
    # Max 5 sentences by default and <= 1000 chars
    assert out.count(".") <= 5
    assert len(out) <= 1000


def test_parser_normalizes_variant_headers_and_title_fallback():
    text = """
    An Interesting Title

    Method
    We used randomized trials.

    Conclusions
    The approach is effective.
    """.strip()
    sections = split_text_into_sections(text)
    # Title fallback: first non-empty line
    assert sections.get("Title") == "An Interesting Title"
    # Header normalization
    assert "We used randomized trials." in sections.get("Methods", "")
    assert sections.get("Conclusion", "").startswith("The approach")


def test_scanned_pdf_returns_empty_sections_and_empty_summary(monkeypatch):
    # Mock low-level extractor to simulate scanned/empty text
    import ingestion.parser as parser_mod

    monkeypatch.setattr(parser_mod, "_extract_text_pdfminer", lambda _: "")
    sections = parser_mod.parse_pdf_into_sections("/tmp/does-not-matter.pdf")
    assert sections == {}
    # With no sections and no abstract, summary is empty
    assert summarize_sections(sections) == ""


def test_summary_includes_results_or_conclusion_when_present():
    sections = {
        "Abstract": "Overview.",
        "Methods": "We did X.",
        "Results": "Accuracy improved by 10%. More details.",
        "Introduction": "Background...",
    }
    out = summarize_sections(sections)
    lowered = out.lower()
    assert ("result" in lowered) or ("improved" in lowered) or ("conclusion" in lowered)

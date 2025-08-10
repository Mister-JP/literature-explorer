from __future__ import annotations

import re
from typing import Protocol


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def extractive_summary(text: str, max_sentences: int = 5, max_chars: int = 1000) -> str:
    """Simple extractive baseline: return first N sentences up to max chars."""
    if not text:
        return ""
    sents = _split_sentences(text)
    output: list[str] = []
    total = 0
    for s in sents[: max_sentences * 2]:
        if not s:
            continue
        if total + len(s) + (1 if output else 0) > max_chars:
            break
        output.append(s)
        total += len(s) + (1 if output else 0)
        if len(output) >= max_sentences:
            break
    return " ".join(output)[:max_chars]


def summarize_sections(sections: dict[str, str]) -> str:
    """Generate a 3–5 sentence extractive summary (<= 1000 chars) from sections.

    Heuristics:
    - Prefer Abstract, Methods, Results, Conclusion, Introduction (in that order)
    - Ensure at least one sentence originates from Results or Conclusion when available
    - Aim for 3–5 sentences by default (fewer if the document lacks sentences)
    """
    if not sections:
        return ""

    preferred_order = ("Abstract", "Methods", "Results", "Conclusion", "Introduction")
    # Build an ordered list of (sentence, source_section)
    sentences_with_section: list[tuple[str, str]] = []
    seen_sentences: set[str] = set()

    # Collect sentences from preferred sections first
    for key in preferred_order:
        text = sections.get(key)
        if not text:
            continue
        for sent in _split_sentences(text):
            if sent in seen_sentences:
                continue
            sentences_with_section.append((sent, key))
            seen_sentences.add(sent)

    # Fallback to any remaining sections if we still have few sentences
    if len(sentences_with_section) < 5:
        for key, text in sections.items():
            if key in preferred_order or not text:
                continue
            for sent in _split_sentences(text):
                if sent in seen_sentences:
                    continue
                sentences_with_section.append((sent, key))
                seen_sentences.add(sent)
                if len(sentences_with_section) >= 10:
                    break

    max_chars = 1000
    max_sentences = 5
    min_sentences = 3

    # Greedily select up to 5 sentences within char budget
    chosen: list[tuple[str, str]] = []
    total = 0
    for sent, key in sentences_with_section:
        add_len = len(sent) + (1 if chosen else 0)
        if total + add_len > max_chars:
            break
        chosen.append((sent, key))
        total += add_len
        if len(chosen) >= max_sentences:
            break

    # Ensure at least one from Results or Conclusion if available
    has_results_or_conclusion = any(
        k in sections and sections[k] for k in ("Results", "Conclusion")
    )
    chosen_has_pref = any(k in ("Results", "Conclusion") for _, k in chosen)
    if has_results_or_conclusion and not chosen_has_pref:
        # Try to insert the first sentence from Results or Conclusion
        target_sent: str | None = None
        for sec in ("Results", "Conclusion"):
            text = sections.get(sec)
            if not text:
                continue
            sents = _split_sentences(text)
            if sents:
                target_sent = sents[0]
                target_sec = sec
                break
        if target_sent:
            # If we have room and < 5 sentences, append; else replace last sentence
            add_len = len(target_sent) + (1 if chosen else 0)
            if len(chosen) < max_sentences and total + add_len <= max_chars:
                chosen.append((target_sent, target_sec))  # type: ignore[name-defined]
            else:
                if chosen:
                    total -= len(chosen[-1][0])
                    chosen[-1] = (target_sent, target_sec)  # type: ignore[name-defined]
                    total += len(target_sent)

    # Ensure at least 3 sentences when possible
    if len(chosen) < min_sentences:
        for sent, key in sentences_with_section[len(chosen) :]:
            add_len = len(sent) + (1 if chosen else 0)
            if total + add_len > max_chars:
                break
            chosen.append((sent, key))
            total += add_len
            if len(chosen) >= min_sentences:
                break

    return " ".join(s for s, _ in chosen)[:max_chars]


class Summarizer(Protocol):
    def summarize(
        self, *, sections: dict[str, str] | None, abstract: str | None
    ) -> str:  # pragma: no cover - interface
        ...


class ExtractiveSummarizer:
    def __init__(self, max_sentences: int = 5, max_chars: int = 1000) -> None:
        self.max_sentences = max_sentences
        self.max_chars = max_chars

    def summarize(self, *, sections: dict[str, str] | None, abstract: str | None) -> str:
        if sections:
            # Use default 3–5 sentences and 1000 chars policy for section-based summaries
            return summarize_sections(sections)
        if abstract:
            return extractive_summary(
                abstract, max_sentences=self.max_sentences, max_chars=self.max_chars
            )
        return ""

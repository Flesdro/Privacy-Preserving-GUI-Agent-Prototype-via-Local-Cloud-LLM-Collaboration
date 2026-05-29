"""Automatic PII / sensitive-field detection.

Rather than hand-labelling which UI elements are sensitive, this module derives
sensitivity from the element text/description using dependency-free regex and
heuristic rules. It is used at parse time (opt-in) to annotate UIElements, so
the privacy machinery does not rely on manual labels.

Detected categories: email, phone, account (card mask / IBAN / long digits),
amount (monetary value), address, name (after an explicit relationship label).
"""
from __future__ import annotations

from dataclasses import replace
import re

from .models import GUIState, UIElement


# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

_PATTERNS: dict[str, re.Pattern[str]] = {
    "email": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    # +1 555 0142 / (021) 555-0142 / 0211234567 — at least 8 digits with separators.
    "phone": re.compile(r"(?<!\d)\+?\d(?:[\d\s\-().]{6,})\d(?!\d)"),
    # Masked card/account (•••• 4821) or a bare long digit run (>=6).
    "account": re.compile(r"(?:[•*x]{2,}\s*\d{2,4})|(?:\b\d{6,}\b)|(?:\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b)"),
    # Monetary amount with a currency symbol: $3,204.55 / £85 / €1,200.00
    "amount": re.compile(r"[$£€]\s?\d[\d,]*(?:\.\d{1,2})?"),
    # Street address: number + 1-3 capitalised words + a street suffix.
    "address": re.compile(
        r"\b\d{1,5}\s+(?:[A-Z][a-z]+\s+){1,3}"
        r"(?:Street|St|Road|Rd|Avenue|Ave|Lane|Ln|Drive|Dr|Way|Blvd|Boulevard)\b"
    ),
    # Person name introduced by an explicit relationship label.
    "name": re.compile(
        r"\b(?:Recipient|To|From|Payee|Owner|Contact|Dr|Mr|Mrs|Ms)\.?\s*:?\s+"
        r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)"
    ),
}

# Topic words that denote private content regardless of structure. Deliberately
# excludes finance-control words (bank, statement, account, payment, transfer,
# amount, balance, bill) that legitimately appear on buttons and titles, so the
# lexicon raises recall without sacrificing precision.
_SENSITIVE_TERMS = {
    "passport", "medical", "medication", "prescription", "clinic", "doctor",
    "therapy", "health", "diagnosis", "scholarship", "grades", "tax", "salary",
    "visa", "geotag", "contacts", "ssn",
}
_TERMS_PATTERN = re.compile(
    r"\b(?:" + "|".join(re.escape(t) for t in _SENSITIVE_TERMS) + r")\b",
    re.IGNORECASE,
)


def detect(text: str) -> list[str]:
    """Return the sorted list of PII categories found in ``text``."""
    if not text:
        return []
    found = [name for name, pattern in _PATTERNS.items() if pattern.search(text)]
    if _TERMS_PATTERN.search(text):
        found.append("topic")
    return sorted(found)


def is_sensitive(element: UIElement) -> bool:
    """True if the element's text or description matches any PII pattern."""
    return bool(detect(element.text) or detect(element.description))


# ---------------------------------------------------------------------------
# Annotation
# ---------------------------------------------------------------------------

def annotate_elements(elements: list[UIElement]) -> list[UIElement]:
    """Return copies of ``elements`` with ``sensitive`` set where PII is found.

    The detected flag is OR-ed with any existing ``sensitive`` value, so manual
    labels are never cleared — auto-detection only adds coverage.
    """
    annotated: list[UIElement] = []
    for element in elements:
        if not element.sensitive and is_sensitive(element):
            annotated.append(replace(element, sensitive=True))
        else:
            annotated.append(element)
    return annotated


def annotate_state(state: GUIState) -> GUIState:
    """Return a copy of ``state`` with auto-detected sensitivity applied."""
    return replace(state, elements=annotate_elements(state.elements))

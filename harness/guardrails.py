"""
Deterministic guardrails that run OUTSIDE the LLM.

Prompts can be ignored by a model; code cannot. These checks enforce the BFSI
governance rules regardless of what the model decides.
"""
from __future__ import annotations

import re

# --- PII masking ------------------------------------------------------------ #
# Order matters: specific patterns first, generic long digit runs last.
_PII_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("PAN", re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")),
    ("CARD", re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b")),
    ("AADHAAR", re.compile(r"\b\d{4}[ -]?\d{4}[ -]?\d{4}\b")),
    ("EMAIL", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.]+\b")),
    ("PHONE", re.compile(r"(?:\+91[ -]?)?\b[6-9]\d{9}\b")),
    ("ACCOUNT", re.compile(r"\b\d{9,18}\b")),
]


def mask_pii(text: str) -> tuple[str, list[str]]:
    """Replace PII with typed placeholders. Returns (masked_text, kinds_found)."""
    found: list[str] = []
    for kind, pattern in _PII_PATTERNS:
        if pattern.search(text):
            found.append(kind)
            text = pattern.sub(f"[{kind}_REDACTED]", text)
    return text, found


# --- Decision requests -------------------------------------------------------- #
_DECISION_REQUEST = re.compile(
    r"\b(approve|sanction|reject|cancel|waive|override|fast[- ]?track|reopen|re-open)\b"
    r".{0,40}\b(loan|application|fee|charges?|it|mine|my)\b",
    re.I,
)


def is_decision_request(text: str) -> bool:
    """True if the customer is asking the assistant to make or change a credit decision."""
    return bool(_DECISION_REQUEST.search(text))


# --- Output check ------------------------------------------------------------- #
_FORBIDDEN_CLAIMS = re.compile(
    r"\b(I|we)\s+(have\s+)?(approved|sanctioned|rejected|waived)\b"
    r"|\bI\s+(will|can)\s+(approve|sanction|reject|waive)\b",
    re.I,
)


def violates_output_policy(text: str) -> bool:
    """True if the assistant claims it made or will make a credit decision."""
    return bool(_FORBIDDEN_CLAIMS.search(text or ""))


SAFE_FALLBACK = (
    "I'm not able to make or change decisions on loan applications. Only our credit team can "
    "do that. I can raise a request for a loan officer to contact you if you'd like."
)

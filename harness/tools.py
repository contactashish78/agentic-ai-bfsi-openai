"""
Approved business tools for the Loan Service Agent.

Rules followed here (BFSI governance):
  * Tools are READ-ONLY lookups or create an escalation ticket. None of them can
    approve, reject, sanction, waive or modify a loan.
  * Each tool returns plain JSON-serialisable data; the harness logs every call.
  * Docstrings matter: aisuite turns the docstring + type hints into the JSON
    schema the model sees, so write them for the model.
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import date, datetime
from functools import lru_cache

from .config import DATA_FILE

_APP_ID = re.compile(r"^LA-\d{4}$")


_DATE_FIELDS = ("submitted_on", "last_updated", "expected_decision_by")


def load_loans() -> dict:
    """Load the synthetic loan data with every date moved relative to today.

    The file is written as of `_dates_as_of`; each date is shifted by
    (today - _dates_as_of) so the demo never shows stale dates.
    """
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    as_of = data.get("_dates_as_of")
    if as_of:
        shift = date.today() - date.fromisoformat(as_of)
        for app in data["applications"].values():
            for field in _DATE_FIELDS:
                if app.get(field):
                    app[field] = (date.fromisoformat(app[field]) + shift).isoformat()
    return data


@lru_cache(maxsize=1)
def _db() -> dict:
    return load_loans()


def _normalise(application_id: str) -> str:
    return application_id.strip().upper().replace(" ", "")


def check_loan_status(application_id: str) -> dict:
    """Look up the current status of a loan application.

    Use this whenever the customer asks about the progress, stage or status of
    their loan application. Never guess a status without calling this tool.

    Args:
        application_id: Loan application ID in the format LA-1234.
    """
    app_id = _normalise(application_id)
    if not _APP_ID.match(app_id):
        return {"found": False, "error": "Invalid application ID format. Expected LA-1234."}
    app = _db()["applications"].get(app_id)
    if not app:
        return {"found": False, "error": f"No application found with ID {app_id}."}
    return {
        "found": True,
        "application_id": app_id,
        "loan_type": app["loan_type"],
        "status": app["status"],
        "stage": app["stage"],
        "submitted_on": app["submitted_on"],
        "last_updated": app["last_updated"],
        "expected_decision_by": app["expected_decision_by"],
        "has_missing_documents": bool(app["missing_documents"]),
        "officer_note": app["officer_note"],
    }


def get_missing_documents(application_id: str) -> dict:
    """List documents the customer still needs to submit for a loan application.

    Args:
        application_id: Loan application ID in the format LA-1234.
    """
    app_id = _normalise(application_id)
    app = _db()["applications"].get(app_id)
    if not app:
        return {"found": False, "error": f"No application found with ID {app_id}."}
    return {
        "found": True,
        "application_id": app_id,
        "loan_type": app["loan_type"],
        "missing_documents": app["missing_documents"],
        "upload_channel": "Customer portal > My Applications > Upload documents",
    }


def get_document_checklist(loan_type: str) -> dict:
    """Return the standard list of documents required for a type of loan.

    Use for general questions such as 'what documents do I need for a home loan?'.

    Args:
        loan_type: One of Home Loan, Personal Loan, Car Loan, Business Loan, Education Loan.
    """
    checklists = _db()["document_checklists"]
    for name, docs in checklists.items():
        if name.lower() == loan_type.strip().lower():
            return {"loan_type": name, "required_documents": docs}
    return {"error": f"Unknown loan type '{loan_type}'.", "supported_loan_types": list(checklists)}


def escalate_to_human(application_id: str, reason: str, priority: str = "normal") -> dict:
    """Create a ticket so a human loan officer contacts the customer.

    Use when: the customer is unhappy or raises a complaint, asks for a loan
    decision to be changed, asks something outside your approved tools, or the
    tool results do not let you answer safely.

    Args:
        application_id: Loan application ID (LA-1234) or "UNKNOWN" if not provided.
        reason: One-line reason for the escalation.
        priority: "normal" or "high". Use high for complaints or financial hardship.
    """
    ticket = f"ESC-{datetime.now():%Y%m%d}-{uuid.uuid4().hex[:5].upper()}"
    return {
        "ticket_id": ticket,
        "application_id": _normalise(application_id) if application_id else "UNKNOWN",
        "priority": priority if priority in ("normal", "high") else "normal",
        "reason": reason,
        "sla": "A loan officer will contact the customer within 1 business day.",
    }


# The allow-list: the ONLY functions the loan agent may execute.
LOAN_TOOLS = [check_loan_status, get_missing_documents, get_document_checklist, escalate_to_human]

"""
Offline tests for the harness: a scripted fake LLM replaces OpenAI so the
loop, guardrails, handoff, skills and audit can be checked without an API key.

    python -m pytest tests -q        (or)    python tests/test_harness_offline.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tempfile  # noqa: E402

from harness import build_default_harness, config  # noqa: E402
from harness.guardrails import is_decision_request, mask_pii, violates_output_policy  # noqa: E402


# keep test runs out of the real audit log
config.AUDIT_FILE = Path(tempfile.mkdtemp()) / "audit_test.jsonl"


def _call(name, args, i=0):
    return NS(id=f"call_{name}_{i}", type="function", function=NS(name=name, arguments=json.dumps(args)))


def _resp(content=None, tool_calls=None):
    return NS(choices=[NS(message=NS(role="assistant", content=content, tool_calls=tool_calls))],
              usage=NS(total_tokens=42))


class FakeClient:
    """Returns pre-scripted responses and records what the harness sent."""

    def __init__(self, script):
        self.script = list(script)
        self.sent = []
        self.chat = NS(completions=NS(create=self._create))

    def _create(self, model, messages, **kw):
        self.sent.append({"messages": messages, "tools": [t["function"]["name"] for t in kw.get("tools", [])]})
        return self.script.pop(0)


def test_guardrails():
    masked, kinds = mask_pii("PAN ABCDE1234F, aadhaar 1234 5678 9012, card 4111 1111 1111 1111, ph 9876543210")
    assert "ABCDE1234F" not in masked and "9876543210" not in masked
    assert set(kinds) >= {"PAN", "AADHAAR", "CARD", "PHONE"}
    assert "LA-1001" in mask_pii("status of LA-1001")[0]
    assert is_decision_request("Please just approve my loan LA-1001")
    assert not is_decision_request("What is the status of my loan?")
    assert violates_output_policy("Good news, I have approved your loan.")
    assert not violates_output_policy("Your loan has been approved by the credit team.")


def test_handoff_tool_skill_and_audit(tmp_path=None):
    fake = FakeClient([
        _resp(tool_calls=[_call("transfer_to_loan_service", {"reason": "status query"})]),
        _resp(tool_calls=[_call("load_skill", {"skill_name": "loan-status-explainer"})]),
        _resp(tool_calls=[_call("check_loan_status", {"application_id": "LA-1001"})]),
        _resp(content="Your application LA-1001 is under review; decision expected by 20 Nov 2026."),
    ])
    h = build_default_harness(client=fake)
    r = h.chat("My PAN is ABCDE1234F. Status of LA-1001?")
    types = [e["type"] for e in r.events]
    assert types[:2] == ["pii_masked", "user"]
    assert "handoff" in types and "skill_loaded" in types and "tool_call" in types
    assert r.agent == "loan_service"
    # the LLM never saw the PAN
    assert all("ABCDE1234F" not in json.dumps(s["messages"]) for s in fake.sent)
    # triage only had triage tools; loan agent got loan tools + load_skill
    assert "check_loan_status" not in fake.sent[0]["tools"]
    assert {"check_loan_status", "load_skill", "transfer_to_triage"} <= set(fake.sent[1]["tools"])
    # skill catalog is in the loan agent's system prompt
    assert "decision-requests" in fake.sent[1]["messages"][0]["content"]
    # tool result made it back into history
    tool_msg = [m for m in h.history if m["role"] == "tool" and m["name"] == "check_loan_status"][0]
    assert json.loads(tool_msg["content"])["status"] == "UNDER_REVIEW"
    assert len(h.audit.read()) == len(r.events)


def test_blocked_tool_and_output_policy():
    fake = FakeClient([
        _resp(tool_calls=[_call("transfer_to_loan_service", {"reason": "approve"})]),
        _resp(tool_calls=[_call("approve_loan", {"application_id": "LA-1001"})]),
        _resp(content="Done! I have approved your loan LA-1001."),
    ])
    h = build_default_harness(client=fake)
    r = h.chat("Please approve my loan LA-1001")
    policies = [e for e in r.events if e["type"] == "policy"]
    assert len(policies) == 3  # decision request, blocked tool, blocked output
    assert "not able to make or change decisions" in r.answer


def test_escalation_and_step_limit():
    fake = FakeClient([
        _resp(tool_calls=[_call("transfer_to_loan_service", {"reason": "complaint"})]),
        _resp(tool_calls=[_call("escalate_to_human",
                                {"application_id": "LA-1004", "reason": "complaint", "priority": "high"})]),
        _resp(content="I've raised ticket ESC-x."),
    ])
    h = build_default_harness(client=fake)
    r = h.chat("I want to complain about LA-1004")
    assert r.escalation and r.escalation["priority"] == "high"

    looping = FakeClient([_resp(tool_calls=[_call("check_loan_status", {"application_id": "LA-1001"}, i)])
                          for i in range(10)])
    h2 = build_default_harness(client=looping, max_steps=3)
    h2.active = "loan_service"
    r2 = h2.chat("status LA-1001")
    assert r2.escalation and "ticket" in r2.answer


if __name__ == "__main__":
    for fn in [test_guardrails, test_handoff_tool_skill_and_audit, test_blocked_tool_and_output_policy,
               test_escalation_and_step_limit]:
        fn()
        print("PASS", fn.__name__)

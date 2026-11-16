"""
The BFSI agent harness.

    customer text
        │  guardrails: PII masking, decision-request detection
        ▼
    ┌──────────── agent loop (max MAX_STEPS LLM calls) ────────────┐
    │  LLM (OpenAI via aisuite) ──► tool call?                     │
    │        ▲                       ├─ allow-listed tool → run it  │
    │        │                       ├─ load_skill → playbook text  │
    │        │                       ├─ transfer_to_X → handoff     │
    │        └────── tool result ◄───┴─ anything else → BLOCKED     │
    └───────────────────────── final answer ───────────────────────┘
        │  guardrail: output policy check
        ▼
    reply + every step written to the audit log

aisuite is used for (a) the provider-agnostic chat call and (b) turning Python
functions into tool schemas. We run the loop ourselves (instead of aisuite's
`max_turns` auto-loop) so that every step can be checked and audited.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import date
from typing import Callable, Optional

from aisuite.utils.tools import Tools

from . import config
from .audit import AuditLog
from .guardrails import SAFE_FALLBACK, is_decision_request, mask_pii, violates_output_policy
from .skills import discover_skills, make_load_skill_tool, skills_catalog
from .tools import LOAN_TOOLS, escalate_to_human


# --------------------------------------------------------------------------- #
# Agent definition
# --------------------------------------------------------------------------- #
@dataclass
class AgentSpec:
    name: str
    instructions: str
    tools: list[Callable] = field(default_factory=list)
    use_skills: bool = False
    handoffs: list[str] = field(default_factory=list)  # agents this one may transfer to


@dataclass
class TurnResult:
    answer: str
    agent: str
    events: list[dict]
    escalation: Optional[dict] = None


def _make_handoff_tool(target: str, description: str) -> Callable:
    def handoff(reason: str) -> dict:
        return {"transferred_to": target, "reason": reason}

    handoff.__name__ = f"transfer_to_{target}"
    handoff.__doc__ = (
        f"Transfer the conversation to the {target} agent. {description}\n\n"
        "Args:\n    reason: One-line summary of the customer's request for the next agent.\n"
    )
    return handoff


# --------------------------------------------------------------------------- #
# Harness
# --------------------------------------------------------------------------- #
class Harness:
    def __init__(
        self,
        agents: list[AgentSpec],
        entry: str,
        model: str = config.MODEL,
        client=None,
        session_id: Optional[str] = None,
        on_event: Optional[Callable[[dict], None]] = None,
        max_steps: int = config.MAX_STEPS,
    ):
        self.agents = {a.name: a for a in agents}
        self.entry = entry
        self.active = entry
        self.model = model
        self.client = client or config.get_client()
        self.session_id = session_id or uuid.uuid4().hex[:8]
        self.audit = AuditLog(self.session_id)
        self.on_event = on_event
        self.max_steps = max_steps
        self.history: list[dict] = []  # conversation without system prompts
        self.skills = discover_skills()
        self._load_skill = make_load_skill_tool(self.skills)
        self._handoff_desc = {a.name: a.instructions.splitlines()[0] for a in agents}

    # ----- per-agent tool registry (the allow-list) ------------------------- #
    def _registry(self, spec: AgentSpec) -> dict[str, Callable]:
        funcs = list(spec.tools)
        if spec.use_skills:
            funcs.append(self._load_skill)
        for target in spec.handoffs:
            funcs.append(_make_handoff_tool(target, self._handoff_desc.get(target, "")))
        return {f.__name__: f for f in funcs}

    def _system_prompt(self, spec: AgentSpec) -> str:
        prompt = f"{spec.instructions}\n\nToday's date: {date.today():%d %b %Y}."
        if spec.use_skills and self.skills:
            prompt += (
                "\n\nAVAILABLE SKILLS (call load_skill with the exact name before handling a "
                "matching request):\n" + skills_catalog(self.skills)
            )
        return prompt

    # ----- events ------------------------------------------------------------ #
    def _emit(self, events: list, etype: str, data, agent: Optional[str] = None) -> None:
        event = {"type": etype, "agent": agent or self.active, "data": data}
        events.append(event)
        self.audit.record(event)
        if self.on_event:
            self.on_event(event)

    def reset(self) -> None:
        self.history.clear()
        self.active = self.entry

    # ----- main entry point --------------------------------------------------- #
    def chat(self, user_text: str) -> TurnResult:
        events: list[dict] = []
        escalation = None

        # 1. Input guardrails (deterministic, before the LLM sees anything)
        masked, kinds = mask_pii(user_text)
        if kinds:
            self._emit(events, "pii_masked", {"types": kinds, "masked_text": masked})
        self._emit(events, "user", masked)
        self.history.append({"role": "user", "content": masked})

        if is_decision_request(masked):
            self._emit(events, "policy", "Credit-decision request detected: agent reminded it has no decision authority.")
            self.history.append({
                "role": "system",
                "content": "POLICY REMINDER: the customer is asking for a credit decision. You cannot approve, "
                           "reject, waive or change loans. Follow the decision-requests skill.",
            })

        # 2. Agent loop
        for step in range(1, self.max_steps + 1):
            spec = self.agents[self.active]
            registry = self._registry(spec)
            messages = [{"role": "system", "content": self._system_prompt(spec)}, *self.history]

            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=Tools(list(registry.values())).tools(),
                temperature=config.TEMPERATURE,
            )
            msg = response.choices[0].message
            usage = getattr(response, "usage", None)
            self._emit(events, "llm_call", {
                "step": step,
                "model": self.model,
                "tool_calls": [tc.function.name for tc in (msg.tool_calls or [])],
                "tokens": getattr(usage, "total_tokens", None),
            })

            # 2a. Final answer -> output guardrail -> done
            if not msg.tool_calls:
                answer = msg.content or ""
                if violates_output_policy(answer):
                    self._emit(events, "policy", {"blocked_output": answer, "replaced_with": SAFE_FALLBACK})
                    answer = SAFE_FALLBACK
                self.history.append({"role": "assistant", "content": answer})
                self._emit(events, "final", answer)
                return TurnResult(answer, self.active, events, escalation)

            # 2b. Tool calls
            self.history.append({
                "role": "assistant",
                "content": msg.content,
                "tool_calls": [
                    {"id": tc.id, "type": "function",
                     "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                    for tc in msg.tool_calls
                ],
            })
            for tc in msg.tool_calls:
                name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}

                if name not in registry:  # allow-list enforcement
                    result = {"error": f"Tool '{name}' is not an approved tool for this agent."}
                    self._emit(events, "policy", {"blocked_tool": name, "arguments": args})
                elif name.startswith("transfer_to_"):
                    result = registry[name](**args)
                    previous, self.active = self.active, result["transferred_to"]
                    self._emit(events, "handoff", {"from": previous, "to": self.active,
                                                   "reason": args.get("reason")}, agent=previous)
                elif name == "load_skill":
                    result = registry[name](**args)
                    self._emit(events, "skill_loaded", args.get("skill_name"))
                else:
                    self._emit(events, "tool_call", {"name": name, "arguments": args})
                    try:
                        result = registry[name](**args)
                    except Exception as exc:  # tool errors go back to the model, not the user
                        result = {"error": f"{type(exc).__name__}: {exc}"}
                    self._emit(events, "tool_result", {"name": name, "result": result})
                    if name == "escalate_to_human":
                        escalation = result
                        self._emit(events, "escalation", result)

                self.history.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": name,
                    "content": json.dumps(result, default=str),
                })

        # 3. Step budget exhausted -> stop safely and hand to a human
        escalation = escalate_to_human("UNKNOWN", "Agent could not complete the request within step limit")
        self._emit(events, "escalation", escalation)
        answer = (f"I wasn't able to fully resolve this, so I've passed it to a loan officer "
                  f"(ticket {escalation['ticket_id']}). {escalation['sla']}")
        self.history.append({"role": "assistant", "content": answer})
        self._emit(events, "final", answer)
        return TurnResult(answer, self.active, events, escalation)


# --------------------------------------------------------------------------- #
# Default BFSI setup: Triage Agent -> Loan Service Agent
# --------------------------------------------------------------------------- #
TRIAGE_INSTRUCTIONS = """\
Front-desk triage assistant for Demo Bank that understands the request and routes it.
You are the Triage Agent for Demo Bank's customer chat.
- Anything about a loan application, INCLUDING complaints, decision disputes and requests for a human about a loan: call transfer_to_loan_service.
- Simple general banking questions (e.g. what is an EMI, branch hours 9:30-16:00 Mon-Sat): answer briefly yourself.
- Anything else (investments, cards, accounts, fraud): do NOT give opinions or advice. Say it is outside this chat's scope and point to the 24x7 helpline 1800-000-0000 or the nearest branch.
Never ask for PAN, Aadhaar, account or card numbers. Keep replies under 4 sentences."""

LOAN_SERVICE_INSTRUCTIONS = """\
Handles loan application status, missing-document and loan-decision queries.
You are the Loan Service Agent for Demo Bank.

RULES (non-negotiable):
1. Use ONLY your tools for facts about an application. Never guess a status, date or document.
2. You cannot approve, reject, sanction, waive fees on, speed up or change any loan. Never claim you did.
3. If the customer has not given an application ID (format LA-1234), ask for it. Do not ask for PAN, Aadhaar, account or card numbers.
4. Escalate to a human (escalate_to_human) for complaints, decision-review requests, or anything your tools cannot answer.
5. Load the matching skill before answering. Be concise, warm and factual. Stop once the request is handled.
6. If the request is not about loans, call transfer_to_triage."""


def build_default_harness(**kwargs) -> Harness:
    triage = AgentSpec(
        name="triage",
        instructions=TRIAGE_INSTRUCTIONS,
        tools=[],  # triage only routes; escalation is owned by the loan_service agent
        handoffs=["loan_service"],
    )
    loan_service = AgentSpec(
        name="loan_service",
        instructions=LOAN_SERVICE_INSTRUCTIONS,
        tools=LOAN_TOOLS,
        use_skills=True,
        handoffs=["triage"],
    )
    return Harness([triage, loan_service], entry="triage", **kwargs)

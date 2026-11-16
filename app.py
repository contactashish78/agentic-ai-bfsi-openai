"""
Streamlit UI for the BFSI agent harness.

    streamlit run app.py

Left: customer chat. Right: live audit trail (every guardrail, LLM call, tool
call, skill load, handoff and escalation for this session).
"""
from __future__ import annotations

import json

import streamlit as st

from harness import build_default_harness
from harness.config import MODEL
from harness.tools import LOAN_TOOLS

st.set_page_config(page_title="Demo Bank · Loan Agent", page_icon="🏦", layout="wide")

ICONS = {
    "user": "🧑", "pii_masked": "🛡️", "policy": "⛔", "llm_call": "🧠", "tool_call": "🔧",
    "tool_result": "📄", "skill_loaded": "📘", "handoff": "🔀", "escalation": "🚨", "final": "✅",
}
COLOURS = {
    "pii_masked": "#be185d", "policy": "#b91c1c", "llm_call": "#475569", "tool_call": "#b45309",
    "tool_result": "#a16207", "skill_loaded": "#6d28d9", "handoff": "#0f766e", "escalation": "#dc2626",
    "final": "#15803d", "user": "#1d4ed8",
}
SCENARIOS = {
    "📊 Loan status": "Hi, what is the status of my loan application LA-1001?",
    "📎 Missing documents": "What documents are still pending for LA-1002?",
    "🛡️ PII in message": "My PAN is ABCDE1234F and phone 9876543210, can you check LA-1005?",
    "⛔ Approve my loan": "Please just approve my loan LA-1001, I need the money urgently.",
    "🚨 Complaint": "This is ridiculous, LA-1004 was rejected without any reason. I want to file a complaint!",
    "💬 General FAQ": "What is an EMI?",
    "❓ Unknown ID": "Check status of LA-9999 please",
}


def _harness():
    if "harness" not in st.session_state:
        st.session_state.harness = build_default_harness()
        st.session_state.chat = []  # [{"role", "content", "events"}]
        st.session_state.tickets = []
    return st.session_state.harness


h = _harness()

# ---------------------------------------------------------------- sidebar --- #
with st.sidebar:
    st.markdown("## 🏦 Demo Bank")
    st.caption("Loan Service Assistant: agentic AI demo")
    st.markdown(f"**Model:** `{MODEL}`  \n**Session:** `{h.session_id}`")
    st.markdown(f"**Active agent:** :blue-background[{h.active}]")
    if st.button("🔄 New conversation", use_container_width=True):
        h.reset()
        st.session_state.chat = []
        st.rerun()

    st.markdown("### Try a scenario")
    for label, prompt in SCENARIOS.items():
        if st.button(label, use_container_width=True):
            st.session_state.pending = prompt

    if st.session_state.tickets:
        st.markdown("### 🚨 Escalations")
        for t in st.session_state.tickets:
            st.error(f"**{t['ticket_id']}** · {t['priority']}\n\n{t['reason']}")

    st.markdown("### Tools vs skills")
    with st.expander("🔧 Tools: the agent's *hands*"):
        st.caption("Python functions our code **executes**. They fetch data or take an action. "
                   "Shown as 🔧 TOOL CALL in the audit trail.")
        for f in LOAN_TOOLS:
            st.markdown(f"- `{f.__name__}`: {(f.__doc__ or '').strip().splitlines()[0]}")
        st.caption("Harness built-ins: `load_skill`, `transfer_to_*`")
    with st.expander("📘 Skills: the agent's *playbook*"):
        st.caption("Markdown instructions the model **reads**. Nothing is executed. They say *how* "
                   "to handle a type of request. Shown as 📘 SKILL LOADED in the audit trail.")
        for s in h.skills.values():
            st.markdown(f"- **{s.name}**: {s.description}")

    with st.expander("🖥️ Display"):
        st.slider("Panel height (px)", 300, 900, 380, step=20, key="panel_height",
                  help="Set to about your browser window height minus 270 px, e.g. 380 on a 1366x768 laptop, 580 on a 1080p screen.")

# ------------------------------------------------------------------- body --- #
chat_col, audit_col = st.columns([3, 2], gap="large")


def render_event(e: dict) -> None:
    colour = COLOURS.get(e["type"], "#475569")
    data = e["data"]
    body = data if isinstance(data, str) else json.dumps(data, indent=1, default=str)
    if len(body) > 600:
        body = body[:600] + " …"
    st.markdown(
        f"<div style='border-left:4px solid {colour};padding:4px 10px;margin:4px 0;"
        f"font-size:12.5px'><b style='color:{colour}'>{ICONS.get(e['type'], '•')} "
        f"{e['type'].replace('_', ' ').upper()}</b> <span style='opacity:.6'>[{e['agent']}]</span>"
        f"<pre style='white-space:pre-wrap;margin:2px 0 0;font-size:12px'>{body}</pre></div>",
        unsafe_allow_html=True,
    )


# Both panels have a fixed height and scroll internally, so a long audit trail
# never makes the page itself scroll (which made the chat jump up).
# Adjust with the "Panel height" slider in the sidebar to fit the projector.
PANEL_HEIGHT = st.session_state.get("panel_height", 380)
st.markdown("""<style>
  [data-testid="stMainBlockContainer"] { padding-top: 3rem; padding-bottom: 1rem; }
</style>""", unsafe_allow_html=True)

with chat_col:
    st.markdown("#### 💬 Customer chat")
    chat_box = st.container(height=PANEL_HEIGHT, border=True, key="chat_panel")
    with chat_box:
        if not st.session_state.chat:
            st.caption("Pick a scenario on the left or type a question below.")
        for m in st.session_state.chat:
            with st.chat_message(m["role"], avatar="🧑" if m["role"] == "user" else "🏦"):
                st.markdown(m["content"])
                if m.get("agent"):
                    st.caption(f"answered by **{m['agent']}** · {len(m['events'])} steps")

prompt = st.chat_input("Ask about your loan application, e.g. 'Status of LA-1001?'")
prompt = prompt or st.session_state.pop("pending", None)

if prompt:
    st.session_state.chat.append({"role": "user", "content": prompt})
    with chat_box:
        with st.chat_message("user", avatar="🧑"):
            st.markdown(prompt)
        with st.chat_message("assistant", avatar="🏦"):
            with st.spinner("Agent is working…"):
                try:
                    result = h.chat(prompt)
                    answer, agent, events = result.answer, result.agent, result.events
                    if result.escalation:
                        st.session_state.tickets.append(result.escalation)
                except Exception as exc:  # show API/config errors instead of a stack trace
                    answer, agent, events = f"⚠️ Error: {exc}", None, []
            st.markdown(answer)
    st.session_state.chat.append({"role": "assistant", "content": answer, "agent": agent, "events": events})
    st.rerun()

with audit_col:
    head, toggle = st.columns([3, 2])
    head.markdown("#### 🧾 Audit trail")
    latest_first = toggle.toggle("Latest first", value=True)
    rows = h.audit.read()
    with st.container(height=PANEL_HEIGHT, border=True, key="audit_panel"):
        if not rows:
            st.info("Every guardrail check, LLM call, tool call, skill load, handoff and escalation "
                    "will appear here and in `logs/audit.jsonl`.")
        for row in (reversed(rows) if latest_first else rows):
            render_event(row)

# Building Intelligent BFSI Applications with the OpenAI API

Webinar material: **LLM call → one tool → single agent → multi-agent → governed harness**,
using the OpenAI API through [aisuite](https://github.com/andrewyng/aisuite).
All customer data in `data/loans.json` is synthetic.

## Setup (once)

New to Python or Jupyter? Follow **`setup_guide.html`** (also `docs/setup_guide.pdf`): step-by-step for Windows/macOS, a Python ↔ .NET/Java cheat sheet, a notebook primer and troubleshooting.

```bash
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env          # then put your OPENAI_API_KEY in .env
python check_setup.py           # verifies Python, packages, .env and one tiny API call
```

## Run

| What | Command |
|---|---|
| Notebooks (modules 1–4) | `jupyter lab notebooks/` |
| Session guide | `session_guide.html` (print-ready) · `docs/session_guide.pdf` |
| Streamlit harness (capstone) | `streamlit run app.py` |
| CLI harness, scripted scenarios | `python cli.py --demo` |
| CLI harness, interactive | `python cli.py` |
| Offline tests (no API key needed) | `python tests/test_harness_offline.py` |

## Layout

```
notebooks/
  01_sdk_basics.ipynb              OpenAI SDK vs aisuite, system/user prompts, structured output
  02_one_business_tool.ipynb       check_loan_status: manual tool loop, then aisuite max_turns
  03_single_agent.ipynb            Loan Service Agent loop: decide / act / observe / escalate / stop
  04_multi_agent_and_harness.ipynb Triage → Loan Service handoff, then a tour of the harness
harness/
  agent.py        Harness loop, AgentSpec, handoffs, default triage + loan_service agents
  tools.py        Approved tools (read-only lookups + escalation ticket)
  skills/*/SKILL.md  Markdown playbooks loaded on demand via load_skill
  guardrails.py   PII masking, decision-request detection, output policy check
  audit.py        JSONL audit log (logs/audit.jsonl)
  config.py       Model and limits from .env
utils.py          print_html / show_messages / show_trace … notebook display helpers
app.py            Streamlit chat + live audit-trail panel
cli.py            Terminal chat
```

## Governance mapping

| Rule | Enforced by |
|---|---|
| Use only approved tools | Per-agent allow-list in `Harness._registry`; unknown calls blocked and logged |
| No approving or rejecting loans | No such tool, `is_decision_request` reminder, `violates_output_policy` replaces the reply |
| Protect customer data | `mask_pii` runs before any text reaches the LLM or the log |
| Human escalation | `escalate_to_human` tool, plus auto-escalation at `MAX_STEPS` |
| Audit | Every event is appended to `logs/audit.jsonl` |

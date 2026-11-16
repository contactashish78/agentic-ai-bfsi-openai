# Session run-sheet (90 min)

| Time | Module | Material | Key moment to land |
|---|---|---|---|
| 0:00–0:05 | Opening | Slides / talk | LLM app → tool → agent → multi-agent → governed harness |
| 0:05–0:20 | 1 · SDK basics | `01_sdk_basics.ipynb` | Raw SDK vs aisuite is one string; **LA-1002 question shows the model can't know your data** |
| 0:20–0:35 | 2 · One business tool | `02_one_business_tool.ipynb` | Model *requests*, our code *executes*; the before/after `compare()` card; aisuite `max_turns` and why we don't use it in BFSI |
| 0:35–0:50 | 3 · Single agent | `03_single_agent.ipynb` | Scenario 2 (two tools chained), 3 (escalation), 4 (refuses to approve) |
| 0:50–1:00 | 4 · Multi-agent | `04_…ipynb` (top half) | Handoff = a tool call; triage decision table |
| 1:00–1:20 | 5 · Capstone harness | `streamlit run app.py` (+ `04_…` bottom half as backup) | Click the scenario buttons; watch the audit panel: PII masked, skill loaded, handoff, policy block, escalation ticket |
| 1:20–1:30 | Wrap-up / Q&A | README governance table | Value is in the harness, not the model |

## Capstone click-path (Streamlit sidebar buttons)
1. **📊 Loan status**: handoff → `loan-status-explainer` skill → `check_loan_status`
2. **🛡️ PII in message**: audit shows `[PAN_REDACTED]`; the LLM never saw it
3. **⛔ Approve my loan**: policy reminder → `decision-requests` skill → polite refusal + offer to escalate
4. **🚨 Complaint**: `complaint-handling` skill → high-priority ticket appears in the sidebar
5. **💬 General FAQ**: triage answers itself, no handoff
6. Open `logs/audit.jsonl` to show the raw audit record

## Pre-flight checklist (day before)
- [ ] `.env` has a working `OPENAI_API_KEY`
- [ ] Run all four notebooks top to bottom and **save them with outputs** (fallback if the network fails)
- [ ] `python cli.py --demo` runs cleanly; check the wording of each answer
- [ ] `streamlit run app.py`: click every scenario button once
- [ ] Delete `logs/audit.jsonl` before going live so the audit panel starts empty

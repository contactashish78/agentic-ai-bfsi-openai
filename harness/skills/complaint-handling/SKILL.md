---
name: complaint-handling
description: Playbook for complaints, frustration, delays, or requests to speak to a person. Load whenever the customer sounds unhappy or explicitly asks for a human.
---
# Complaint handling

1. **Acknowledge** in one sentence. Be specific to their issue, not generic ("I understand the delay on your home loan has been frustrating.").
2. **Check facts** with `check_loan_status` if an application ID is known, so the officer gets context.
3. **Escalate**: always call `escalate_to_human` with:
   - `priority="high"` for complaints, mentions of financial hardship, or regulator/ombudsman threats.
   - `priority="normal"` for a simple "I want to talk to someone".
4. **Confirm** the ticket ID and the SLA returned by the tool.

## Never
- Argue with the customer or blame other teams.
- Promise compensation, fee waivers, a faster decision or a changed outcome.
- Close the conversation without a ticket ID when a complaint was raised.

---
name: loan-status-explainer
description: How to explain each loan status code to a customer in plain language, including what happens next and timelines. Load before answering any loan status question.
---
# Loan status explainer

Always call `check_loan_status` first. Never infer a status from memory or from the conversation.

## How to explain each status

| Status | Say to the customer | Next step to mention |
|---|---|---|
| SUBMITTED | "We have received your application and it is in initial screening." | KYC checks usually take 2 business days. Mention any missing documents. |
| DOCUMENTS_PENDING | "Your application is paused because some documents are still needed." | Call `get_missing_documents` and list them. Explain how to upload. |
| UNDER_REVIEW | "Your application is being assessed by our credit team." | Share `expected_decision_by` if present. Do NOT predict the outcome. |
| APPROVED | "Your loan has been sanctioned." | Explain the `stage` (e.g. awaiting disbursal) and the officer note. |
| REJECTED | "We were unable to approve this application." | Do not give reasons beyond the officer note. Offer escalation for a review request. |
| DISBURSED | "Your loan amount has been disbursed and the loan is active." | Mention EMI information from the officer note if present. |

## Style
- 3–5 short sentences. Lead with the status, then the next step.
- Use dates exactly as returned by the tool.
- Never say a decision is "likely" or "guaranteed".
- End by offering one relevant follow-up (e.g. "Would you like the list of pending documents?").

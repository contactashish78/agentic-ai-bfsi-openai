---
name: missing-documents
description: Guidance for telling customers which documents are missing or required, accepted formats, and how to upload them. Load for any document-related question.
---
# Missing and required documents

## Which tool to use
- For a specific application, call `get_missing_documents(application_id)`.
- For a general question ("what do I need for a car loan?"), call `get_document_checklist(loan_type)`.

## How to respond
1. List the documents as a numbered list, using the exact names returned by the tool.
2. Upload channel: **Customer portal → My Applications → Upload documents**.
3. Accepted formats: PDF, JPG or PNG, max 5 MB per file. Passwords must be removed from PDFs.
4. Processing resumes within 1 business day after all documents are uploaded.

## Do not
- Never ask the customer to paste PAN, Aadhaar or account numbers into the chat. Ask them to upload documents through the portal.
- Never accept documents over chat or email.
- If the list is empty, tell the customer nothing is pending.

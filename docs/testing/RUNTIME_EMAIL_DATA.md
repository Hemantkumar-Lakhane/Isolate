# Runtime Synthetic Email Data & Email Summarizer Testing Guide

## Overview

This document describes the runtime synthetic email data architecture and how the **Email Summarizer** workflow executes against fixture data without requiring a live Gmail connection or Google OAuth credentials.

---

## 1. Why Synthetic Email Data Exists

To test complex AI workflow orchestration, prompt execution, agent reasoning, and database run persistence, developers need a reliable, deterministic email dataset. Synthetic email data enables:
* End-to-end testing of workflow execution independently of external Google OAuth credentials or rate limits.
* Testing edge cases (urgent escalations, missing fields, customer complaints, empty inboxes, malformed JSON).
* Immediate developer setup (`python db/seed/email_seed.py`) with zero API key or credential prerequisites.

---

## 2. Synthetic Email Data vs. Real Gmail

| Feature | Synthetic Runtime Fixture | Real Gmail Integration |
| :--- | :--- | :--- |
| **Data Source** | Local JSON file (`db/seed/data/email_messages.json`) | Google Gmail API (`gmail.googleapis.com`) |
| **Connector** | `email_get_synthetic_messages` in `local_dev_tools.py` | `GmailConnector` in `connectors.py` |
| **Auth Requirement** | None (`is_test_data: true`) | Google OAuth2 Access Token / Refresh Token |
| **Database Impact** | Zero (Does not populate PostgreSQL org tables) | Encrypted `tool_connections` vault record |
| **Workflow Contract** | Identical DAG & Agent Input Schema | Identical DAG & Agent Input Schema |

---

## 3. Architecture Diagrams

### Synthetic Test Path (Development / Testing)

```
Synthetic Dataset (db/seed/data/email_messages.json)
      ↓
Local Email Tool (email_get_synthetic_messages)
      ↓
Email Summarizer Workflow (workflows/dags/email_summarizer.json)
      ↓
Agents (ResearchAgent → SummarizerAgent → MemoryAgent)
      ↓
Workflow Run & Agent Records (PostgreSQL workflow_instances & agent_run_records)
      ↓
SMBFlow UI (http://localhost:5173/workflows)
```

### Production Gmail Path (Live Integration)

```
Real Gmail (gmail.googleapis.com)
      ↓
Gmail Connector (GmailConnector via MultiFernet Vault)
      ↓
Same Workflow (workflows/dags/email_summarizer.json)
      ↓
Same Agents (ResearchAgent → SummarizerAgent → MemoryAgent)
      ↓
Same Workflow Run (PostgreSQL workflow_instances & agent_run_records)
```

---

## 4. Dataset Location & Regeneration

* **Generator Script**: `db/seed/email_seed.py`
* **Output Location**: `db/seed/data/email_messages.json`
* **Deterministic Seed**: `random.seed(42)` ensures identical output every time.
* **Regeneration Command**:
  ```bash
  python db/seed/email_seed.py
  ```
  or check seed status:
  ```bash
  python db/seed/run_all_seeders.py --check
  ```

---

## 5. Dataset Structure

Each record in `email_messages.json` is formatted as follows:

```json
{
  "id": "seed-email-001",
  "message_id": "seed-msg-001",
  "thread_id": "seed-thread-001",
  "from": "alice.smith@clientcorp.example.test",
  "to": "support@smbflow.test",
  "subject": "Help with login issue on user dashboard",
  "body": "Hi team, I am unable to log in to our dashboard...",
  "received_at": "2026-09-08T07:00:00Z",
  "labels": ["INBOX", "SUPPORT"],
  "scenario": "customer_support_request",
  "priority": "normal",
  "data_origin": "synthetic",
  "is_test_data": true,
  "dataset": "email_workflow_demo"
}
```

---

## 6. Triggering the Email Summarizer Workflow

### A. Via REST API
```http
POST /api/v1/workflows/trigger
Content-Type: application/json
Authorization: Bearer <token>

{
  "workflow_name": "email_summarizer",
  "signal_data": {}
}
```

### B. Via SMBFlow UI
1. Open `http://localhost:5173/workflows`.
2. Locate **Synthetic Email Summarizer Pipeline**.
3. Click **Trigger Workflow**.

---

## 7. Expected Structured Agent Output

Upon execution, the `SummarizerAgent` returns structured output in `agent_run_records.output_dict`:

```json
{
  "summary": "Processed 40 emails. Found 2 urgent escalations and 6 high-priority invoice and support issues.",
  "total_emails": 40,
  "important_emails": [
    {
      "message_id": "seed-msg-005",
      "subject": "URGENT: System outage affecting 500+ active users",
      "reason": "Critical outage affecting MC-902 account",
      "priority": "urgent"
    }
  ],
  "action_required": [
    {
      "message_id": "seed-msg-007",
      "subject": "Discrepancy on Invoice #INV-4821",
      "action": "Verify contracted rate ($3,800 vs $4,500) and issue adjusted invoice."
    }
  ],
  "categories": {
    "customer": 8,
    "finance": 6,
    "sales": 4,
    "operations": 8,
    "scheduling": 4,
    "other": 10
  }
}
```

---

## 8. Testing Edge Cases

### A. Empty Dataset Test
If `email_messages.json` contains `[]` or is missing, `email_get_synthetic_messages` returns:
```json
{
  "messages": [],
  "total_messages": 0,
  "data_origin": "synthetic",
  "is_test_data": true,
  "dataset": "email_workflow_demo"
}
```
The workflow completes gracefully without crashing, and `SummarizerAgent` reports `"0 emails found"`.

### B. Malformed Message Test
If optional fields (`thread_id`, `labels`, `scenario`) are omitted, default fallback handlers in `local_dev_tools.py` and `SummarizerAgent` fill missing fields cleanly.

---

## 9. Security & Isolation Rules

1. **No External Writes**: The synthetic test path NEVER calls external Gmail endpoints or sends network traffic to Google.
2. **No Production Database Contamination**: Fixture emails exist only in `db/seed/data/email_messages.json` and are read in-memory. They are never written into production tenant DB tables (`organizations`, `patient_contacts`, `tool_connections`).
3. **Multi-Tenant Ownership**: Generated workflow runs (`workflow_instances`) and step records (`agent_run_records`) are strictly scoped to the triggering user's `organization_id`.

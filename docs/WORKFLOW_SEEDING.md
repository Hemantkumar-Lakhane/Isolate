# Workflow Seed Data Guide

## Overview
This document explains how to generate and load synthetic seed data for each implemented workflow in the **SMBFlow** demo environment. Seed data lives in `db/seed/data/` as JSON files and is consumed by the local‑dev tool registry in `integrations/local_dev_tools.py`.

## Implemented Workflows & Required Seed Files
| Workflow | Seed File(s) | What it Covers |
|----------|--------------|----------------|
| **Inbound Lead‑to‑Demo** | `inbound_leads.json` | Synthetic website‑form leads with varied `form_type`, `requested_demo` flags, missing fields, free‑email domains, spam examples, and proper UTM metadata. |
| **Email Summarizer** | `email_messages.json` | 40 synthetic email messages spanning support tickets, complaints, escalations, finance notices, internal ops alerts, and low‑priority newsletters. Each entry includes `scenario`, `priority`, and `data_origin` flags. |
| **SaaS Account & Deal Views** (used by reporting dashboards) | `saas_accounts.json`, `saas_deals.json` | Accounts with health labels (`critical`, `at_risk`, `healthy`) and deals with stall flags. |
| **Retail Inventory & Sales** | `retail_products.json` | Product SKUs with risk labels (`stockout`, `overstock`, `healthy`). |
| **Healthcare Patients & Appointments** | `healthcare_patients.json`, `healthcare_appointments.json` | Patient records with risk stratification and upcoming appointments. |
| **Finance Expenses** | `finance_expenses.json` | Transactions with anomaly flags and department info. |
| **Real‑Estate Listings & Leases** | `re_listings.json`, `re_leases.json` | Listings with risk labels and lease data (flight‑risk, expiry). |
| **Email‑Workflow Demo** (used by `email_summarizer` DAG) | **Same as Email Summarizer** (`email_messages.json`). |

> **Important:** Each seed file is purpose‑built for its corresponding workflow. Do **not** reuse a single dataset for unrelated workflows – this ensures realistic variations and prevents cross‑workflow contamination.

## Generating Seed Data
The repository ships a convenience script: `db/seed/run_all_seeders.py`. It reads the individual industry seed generators (`*_seed.py`) and writes JSON fixtures to `db/seed/data/`.

### One‑Time Generation
```powershell
# From the repository root
python db/seed/run_all_seeders.py
```
Running without arguments generates **all** industry data. You can limit to a single industry, e.g.:
```powershell
python db/seed/run_all_seeders.py --industry email   # only email_messages.json
```
Use `--check` to simply list which files already exist and how many records they contain.

### Integrated into `start.ps1`
`start.ps1` now automatically runs the seeder before launching the backend and frontend. This guarantees fresh seed data on every local start:
```powershell
python db/seed/run_all_seeders.py
```
If the seeder exits with a non‑zero status, the script aborts and prints an error.

## Data Quality Checklist
- **Domain realism** – free‑email domains (`gmail.com`, `yahoo.com`) are flagged as low‑quality in lead data.
- **UTM completeness** – every inbound lead includes `utm_source`, `utm_medium`, and `utm_campaign` (or explicit `null`).
- **Scenario diversity** – email messages cover at least 5 distinct scenarios (`customer_support_request`, `customer_complaint`, `payment_reminder`, `vendor_communication`, `urgent_operational_issue`).
- **Size variation** – each JSON file contains a mix of high‑priority, normal, and low‑priority records to exercise workflow branching.
- **Synthetic flag** – `data_origin: "synthetic"` and `is_test_data: true` are present so the system never contacts real users.

## Running a Workflow Locally
1. **Start the environment** – simply run:
   ```powershell
   .\start.ps1
   ```
   The script will:
   - Ensure Redis is running.
   - Generate seed data via `run_all_seeders.py`.
   - Launch the FastAPI backend.
   - Launch the Vite/React frontend.
2. **Trigger a workflow** – use the Swagger UI (`http://localhost:8000/docs`) or the provided API endpoint to fire a DAG, e.g. `POST /api/v1/workflows/run` with payload `{ "workflow_name": "inbound_lead_to_demo" }`.
3. **Inspect results** – check the dashboard or query the `workflow_instances` table in Postgres to see persisted run metrics.

## Adding New Seed Data for Future Workflows
When you introduce a new workflow (e.g. *Founder Content‑to‑Demand*), follow these steps:
1. **Create a JSON fixture** in `db/seed/data/` with a clear naming convention, e.g. `founder_content_requests.json`.
2. **Add a seeder script** (`founder_content_seed.py`) that populates the fixture with at least 20 varied records (different founder notes, content goals, CTA types, and quality flags).
3. **Register the tool** in `integrations/local_dev_tools.py` by adding a new async function `founder_content_get_requests` that loads the fixture via `_load_seed`.
4. **Update `run_all_seeders.py`** – add an entry to the `seeders` dict and ensure the script runs it.
5. **Document** the new seed file and its purpose in this `WORKFLOW_SEEDING.md` under *Implemented Workflows*.

---
*Generated on 2026‑09‑12 – keep this file under version control to share seeding expectations with the team.*

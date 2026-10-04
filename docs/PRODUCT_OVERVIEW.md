# SMBFlow — Product Overview

## 1. Product Vision
**SMBFlow** (Agency Automation Suite) is a general-purpose, multi-tenant Agentic Workflow Automation Platform designed for Small-to-Medium Businesses (SMBs) across diverse industries (Medical Tourism, SaaS Startups, Retail, Professional Services, etc.).

## 2. Core Mental Model
The platform operates on a domain-neutral foundation:
```text
SMBFlow Core ──► Organization ──► Business Profile ──► Connect Tools ──► Workflow Library ──► Agents + Tools + Policies ──► HITL Gate ──► Execute ──► Audit
```

## 3. Dynamic Verticals & Modules
- **Core Platform**: Reusable multi-tenancy, authentication, connection vault, workflow engine, agent capabilities, policy engine, approval queue, evidence ledger.
- **Domain Modules (`enabled_modules`)**: Industry-specific domain features enabled per organization.
  - **Medical Tourism (`medical_tourism`)**: First real vertical pilot use case (Fertility/IVF & Revision Orthopedics care coordination in India).
  - **SaaS Startup (`sales`, `customer_success`)**: Pipeline velocity, customer support, and onboarding.

## 4. Key Differentiators
- **Tools-First Onboarding**: Tool connections are first-class capabilities verified before workflows are enabled.
- **8 Reusable Agent Capabilities**: Customer Outreach, Customer Support, Marketing Outreach, Summarizer, Recommendation (Ops), Comparison (Quote), HR, Operations.
- **Human-in-the-Loop Governance**: External actions and high-risk decisions require explicit human approval via the Action Center.
- **Zero Fake Data**: Clean empty states rendered across all dashboards when no real backend data exists.

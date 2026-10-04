# Agency Automation Suite
## Unified Product Requirements Document: Growth Edition and Startup Edition

**Version:** 3.0  
**Status:** Development-ready strategic and technical specification  
**Audience:** Founder, product lead, software engineering interns, AI/workflow interns, UX/UI interns, QA/DevOps interns  
**Product category:** Multi-tenant, governed AI Growth Operations platform  

---

# 1. Executive Decision

## 1.1 One platform, two product editions

Agency Automation Suite will be built as **one secure, multi-tenant platform**, not as two separate products or two codebases.

The same core infrastructure will serve two customer segments:

1. **Startup Edition** — opinionated, self-serve, template-driven workflows for pre-seed through Series A startups.
2. **Growth Edition** — configurable, governed, managed workflows for B2B SaaS and tech-enabled professional-service companies with approximately $5M–$30M annual revenue.

The editions differ in onboarding, workflow complexity, integrations, controls exposed in the UI, support model, quotas, and price. They must share the same underlying tenant security, connector framework, workflow runtime, policy system, evidence ledger, cost controls, and attribution layer.

```text
                    Shared Agency Automation Suite Core
+-----------------------------------------------------------------------+
| Multi-tenancy | RBAC | Connector Framework | Workflow Runtime         |
| Agent Registry | Policy Engine | Approvals | Evidence Ledger          |
| Evaluation Console | Cost Controls | Attribution | Data Quality Center  |
+----------------------------+------------------------------------------+
                             |
          +------------------+------------------+
          |                                     |
          v                                     v
+----------------------------+    +--------------------------------------+
| Startup Edition            |    | Growth Edition                       |
| Template-led, self-serve   |    | Configurable, guided, managed        |
| Founder / founding GTM     |    | Marketing, sales, RevOps, leadership |
| Low setup and lower price  |    | Advanced policies and integrations   |
+----------------------------+    +--------------------------------------+
```

## 1.2 Product positioning

> Agency Automation Suite turns founder, marketing, and inbound activity into qualified, attributable pipeline through safe, governed AI workflows.

The platform is not a generic chatbot, a generic “AI content generator,” an unrestricted autonomous agent, or a replacement for CRM, accounting, email, or social platforms.

Its differentiation is:

- Controlled execution inside the customer’s existing stack.
- Explicit agent permissions and tool allowlists.
- Human approval for consequential external actions.
- Evidence, auditability, and source-linked recommendations.
- Outcome measurement: qualified leads, meetings, opportunities, pipeline, response time, and workflow quality.
- Repeatable playbooks for common startup and growth-company use cases.
- A natural upgrade path from startup to growth company without migration to a different product.

---

# 2. Customers and Editions

## 2.1 Startup Edition

### Ideal customer profile

- Pre-seed, seed, or Series A startup.
- Roughly 2–30 employees.
- B2B SaaS, AI SaaS, developer tools, marketplaces, technology-enabled services, or early-stage professional services.
- Founder-led marketing/sales or a very small GTM team.
- Uses HubSpot **or** Pipedrive, Gmail, Google Calendar, a website form, and LinkedIn/manual social distribution.
- Needs a repeatable way to create demand, respond to inbound leads, launch product updates, and understand weekly growth without hiring a full GTM team.

### Buyer and primary users

- Founder / CEO.
- Founding marketer.
- Founding salesperson.
- Product marketer or growth lead.

### Product promise

> From founder expertise and inbound interest to qualified demos and attributable pipeline—without hiring a full-time growth operations team.

### Startup Edition product rules

- Setup target: first live workflow in under 45–60 minutes after integrations are authorized.
- Self-serve onboarding and opinionated templates.
- Simple defaults; advanced governance exists but is not shown until needed.
- Draft-first behavior for content and external communication.
- Lower limits and clear quotas to protect costs.
- One or two primary workflows active at a time during early plans.

## 2.2 Growth Edition

### Ideal customer profile

- B2B SaaS or tech-enabled professional-service firm.
- Approximately $5M–$30M annual revenue.
- Roughly 20–150 employees.
- HubSpot required for early pilots; Google Workspace and Slack strongly preferred.
- Existing sales, marketing, and RevOps processes but inconsistent data, manual handoffs, weak content-to-pipeline linkage, and limited internal AI/automation capacity.

### Buyer and primary users

- Founder/CEO.
- VP Sales / Head of Revenue.
- Head of Growth / VP Marketing.
- RevOps lead.
- Customer success leader in later releases.

### Product promise

> A governed AI Pipeline Operations layer that converts demand into qualified, attributable pipeline while preserving brand control, CRM integrity, and human oversight.

### Growth Edition product rules

- Guided onboarding and optional managed implementation.
- Configurable qualification/routing/approval policies.
- More integration capacity, team roles, and workflow runs.
- Full control-plane UI: agent registry, policy engine, evidence ledger, evaluation dashboard, and cost controls.
- Later expansion into account-growth and finance/operations workflows.

## 2.3 Edition comparison

| Dimension | Startup Edition | Growth Edition |
|---|---|---|
| Company stage | Pre-seed to Series A | $5M–$30M revenue |
| Typical team | 2–30 | 20–150 |
| Buyer | Founder / founding GTM | Growth, sales, RevOps, CEO |
| Setup | Self-serve, under 60 minutes | Guided, days to weeks depending on data |
| Primary job | Generate first repeatable demand and convert inbound to demos | Improve qualified pipeline, routing, attribution, governance |
| Workflow model | Templates with limited configuration | Configurable workflows, policies, teams, and handoffs |
| Integrations | HubSpot or Pipedrive, Gmail, Calendar, form, GA4 | HubSpot, Gmail, Calendar, Slack, GA4; later more connectors |
| Governance UI | Safe preset defaults + simple automation controls | Full registry, policy engine, evaluations, approval delegation |
| Support | Documentation, office hours, limited support | Implementation, managed operations, customer success |
| Pricing | Lower platform fee and usage caps | Platform + workflow package + managed-service option |

---

# 3. Core Business Problem

## 3.1 Shared problems solved

Both startups and growth companies commonly experience:

- Inbound leads arrive but are not quickly qualified, routed, or followed up.
- CRM data is incomplete or stale.
- Founder/executive expertise does not become a consistent content and demand engine.
- Content is disconnected from conversion paths and pipeline reporting.
- Marketing, sales, calendar, email, analytics, and CRM data are fragmented.
- Teams need AI assistance but do not trust unreviewed external actions.
- Existing AI tools generate outputs but do not execute controlled workflows or prove business value.

## 3.2 Shared outcome loop

```text
Founder insight / campaign / inbound source
        ↓
Content or conversion asset
        ↓
Tracked CTA and lead capture
        ↓
Lead enrichment, qualification, and routing
        ↓
Approved follow-up and scheduling
        ↓
Meeting, opportunity, and pipeline reporting
        ↓
Insights that improve the next content and workflow cycle
```

## 3.3 Non-goals for initial release

- Do not replace CRM, email, accounting, or social platforms.
- Do not build a blank-slate no-code agent builder in the first release.
- Do not allow agents to run shell commands, arbitrary browser automation, arbitrary code, or unrestricted third-party actions.
- Do not auto-send broad outbound campaigns, unsolicited DMs, or public posts without configured approval.
- Do not promise guaranteed pipeline/revenue.
- Do not include finance automation in Startup Edition v1.
- Do not build 50+ integrations before validating core workflows.

---

# 4. Core Product Principles

1. **One workflow loop before broad expansion:** Build and validate demand-to-pipeline before finance, HR, support, or general operations.
2. **Outcome over activity:** Measure qualified leads, meetings, opportunities, pipeline, response time, and customer action—not words generated or social likes alone.
3. **Draft-first and approval-first:** AI can prepare work. Important external actions pass through policy and approvals.
4. **Evidence before claims:** Content, scoring, and recommendations must show their data sources and gaps.
5. **Existing systems stay authoritative:** CRM and connected systems remain systems of record.
6. **Least privilege:** Each agent receives only required sources and allowed actions.
7. **Evaluation before greater autonomy:** An agent earns autonomy through measured quality, not a configuration checkbox alone.
8. **Safe failure:** Missing data, low confidence, failed sync, or ambiguous policy means pause/escalate—not guess or act.
9. **Cost is a product feature:** Track and limit model, enrichment, media, and integration costs by tenant/workflow.
10. **Progressive disclosure:** Startup Edition is simple on the surface; Growth Edition exposes deeper controls without changing the secure underlying foundation.

---

# 5. Shared Platform Architecture

## 5.1 High-level design

```text
+------------------------------------------------------------------------+
|                   Web Application (Next.js / React)                    |
| Startup UX: Templates and simple dashboards                             |
| Growth UX: Configurable workflows and full governance controls         |
+----------------------------------+-------------------------------------+
                                   |
                                   v
+------------------------------------------------------------------------+
|                    API and Tenant Access Layer                         |
| FastAPI | Auth | Roles | Tenant Context | Rate Limits | OpenAPI         |
+----------------------------+-----------------------------+-------------+
                             |                             |
                             v                             v
+------------------------------+        +----------------------------------+
| Platform Control Plane       |        | Workflow Runtime                 |
| - Agent Registry             |        | - Explicit state machine         |
| - Policy Engine              |        | - Job queue / workers            |
| - Approval Center            |        | - Retries / timeouts             |
| - Evidence Ledger            |        | - Human escalation               |
| - Evaluation Console         |        | - Cost accounting                |
| - Kill Switches              |        +----------------+-----------------+
| - Plan/Quota Manager         |                         |
+---------------+--------------+                         v
                |                   +------------------------------------+
                v                   | Connector Trust Layer              |
+--------------------------------+  | OAuth | token vault | webhook verify |
| Postgres + RLS + pgvector     |  | tool allowlists | sync health        |
| Object storage + audit logs   |  +----------------+-------------------+
+--------------------------------+                   |
                                                     v
             HubSpot | Pipedrive | Gmail | Google Calendar | Slack | GA4
             Website Forms | LinkedIn / supported social APIs | later connectors
```

## 5.2 Recommended technology stack

| Layer | Recommendation | Requirement |
|---|---|---|
| Frontend | Next.js, React, TypeScript | Responsive web app, role-based UI |
| Backend | Python FastAPI | REST APIs, OpenAPI, validation |
| Auth | Supabase Auth or Auth0 | OAuth/OIDC, invitations, RBAC |
| Database | PostgreSQL with Row-Level Security | Source of truth; `tenant_id` in all customer records |
| Vector retrieval | pgvector initially | Tenant-filtered retrieval only |
| Background runtime | Temporal or Celery/RQ + Redis | Long-running jobs, scheduling, retry |
| Workflow orchestration | LangGraph or explicit state machine | Inspectable, resumable workflows |
| Object storage | S3-compatible storage | Tenant-scoped uploads, signed URLs |
| Secrets | KMS-backed secrets manager | Encrypt OAuth credentials/tokens |
| Observability | OpenTelemetry + Sentry + structured logs | Workflow traces, error tracking, safe logging |
| Deployment | Vercel + AWS/Render/Fly.io | Staging and production environments |

## 5.3 Non-negotiable technical rules

- Every tenant record, file, vector/document, job, trace, and action includes `tenant_id`.
- Row-Level Security must enforce tenant access in the database.
- Tenant context must come from authenticated identity, not a user-supplied request field.
- Every connector credential is tenant-scoped, encrypted, and revocable.
- Every external side effect goes through policy evaluation and Action Execution service.
- Every LLM output used by a workflow is JSON-schema validated.
- Every important action has an idempotency key and an evidence record.
- Every workflow can be paused, cancelled, retried, or escalated.
- Every production agent has a human owner, a cost budget, and a kill switch.

---

# 6. Shared Control Plane

## 6.1 Agent Registry

The Agent Registry is a core system, even when Startup Edition shows a simplified “Automations” page.

### Required fields

| Field | Description |
|---|---|
| Agent ID/name | Unique ID and human-readable label |
| Tenant ID | Organization owner |
| Edition eligibility | Startup, Growth, or both |
| Business objective | Specific job/outcome |
| Human owner | Accountable internal/customer user |
| Lifecycle | Draft, Test, Active, Paused, Deprecated, Retired |
| Model/version | LLM and configuration |
| Prompt/workflow version | Versioned implementation |
| Allowed data | Allowed integration/data-source list |
| Allowed tools | Action/tool allowlist |
| Autonomy level | Draft-only, approval-required, limited autonomous |
| Policy version | Rules currently governing actions |
| Evaluation result | Latest quality/safety score |
| Cost budget | Per run/day/month limits |
| Kill-switch state | Enabled/disabled |

## 6.2 Policy Engine

Every possible external action is evaluated before execution.

### Policy inputs

- Tenant and edition.
- Agent identity/version.
- Action type.
- User/agent role.
- Data classification.
- Recipient and recipient count.
- Message volume.
- Confidence score.
- Time of day/business hours.
- CRM object type/number of records.
- Campaign state.
- Plan/quota status.

### Policy outcomes

```text
ALLOW
ALLOW_WITH_LOG
REQUIRE_APPROVAL
REQUIRE_ADDITIONAL_DATA
BLOCK
```

### Default policies

| Action | Startup Edition default | Growth Edition default |
|---|---|---|
| Generate content draft | Allow | Allow |
| Publish social post | Marketing/founder approval | Configurable approval policy |
| Create CRM lead | Allow only if workflow/template and score threshold permit | Configurable policy based on score/data quality |
| Update CRM record | Limited single-record update only | Configurable; no bulk updates by default |
| Send individual external email | Approval required | Approval required initially; later configurable after evaluation |
| Create calendar invitation | Approval required | Approval required initially |
| Bulk outreach | Block in initial release | Block in initial release |
| Paid-ad spend change | Block | Block |
| Financial action | Not available | Block until Finance Edition controls exist |

## 6.3 Approval Center

Approvers must view the exact proposed action—not a vague summary.

### Required features

- Pending, approved, rejected, failed, expired, cancelled views.
- Action target: exact recipient/record/channel.
- Exact message/payload.
- Agent reasoning summary, confidence, and source references.
- Edit before approval.
- Approve/reject with feedback.
- Approval delegation and expiration.
- Final provider execution result.
- Immutable audit history.

## 6.4 Evidence Ledger

For each workflow run/action, store:

- Trigger and input references.
- Agent and prompt/workflow version.
- Data/documents retrieved.
- Structured output.
- Policy result.
- Approval decision.
- Request sent to external provider.
- Provider response and final state.
- Errors/retries.
- Cost.

## 6.5 Evaluation Console

Agents cannot gain autonomy without evaluation.

### Required functions

- Store agent-specific test cases.
- Store human labels and corrections.
- Run model/prompt versions against test sets.
- Compare versions.
- Show structured-output validity, safety, quality, and cost.
- Block promotion when thresholds fail.
- Downgrade an agent to approval-only when production quality declines.

## 6.6 Data Quality Center

Required checks:

- Integration health and last successful sync.
- Missing CRM fields required for lead routing.
- Invalid email or missing company information.
- Duplicate contacts/accounts.
- Missing/invalid UTM tags.
- Stale lifecycle stage or owner.
- Broken links or failed forms.
- Connector scopes insufficient for workflow.

When data quality is insufficient, the agent must pause or request review rather than make a high-impact decision.

---

# 7. Integrations and Input Capture

## 7.1 Input sources

The platform captures input through:

1. OAuth-connected apps.
2. Verified webhooks.
3. Scheduled/incremental API sync.
4. Onboarding forms.
5. CSV/Google Sheets fallback imports.
6. File uploads: brand guides, case studies, product briefs, call notes.
7. Approved website ingestion.
8. Manual user feedback, corrections, and approvals.

## 7.2 Initial integration roadmap

| Priority | Integration | Startup Edition | Growth Edition | Initial actions |
|---|---|---|---|---|
| P0 | HubSpot | Choose HubSpot or Pipedrive | Required for initial pilots | Controlled contact/lead/task/note writes |
| P0 | Pipedrive | Supported alternative CRM | Later/optional | Controlled contact/lead/task writes |
| P0 | Gmail / Google Workspace | Required | Required | Draft email; send only via approval |
| P0 | Google Calendar | Required | Required | Read free/busy; create invite only via approval |
| P0 | Website form/webhook | Required | Required | Inbound lead ingestion |
| P0 | Google Analytics 4 | Recommended | Required | Read-only attribution data |
| P1 | Slack | Optional alerts | Required/recommended | Internal alerts/approval notices |
| P1 | LinkedIn/supported social APIs | Content metrics/publish where official access permits | Same + team workflows | Publishing only with approval and official API path |
| P2 | Stripe | Optional subscription signal | Account-growth signal | Read-only initially |
| P2 | Intercom | Not initial | Later account/support signal | Read-only/draft actions |
| P3 | QuickBooks/Xero | Not initial | Finance Edition | Read-only/draft collection actions |

## 7.3 Connector requirements

Every connector must implement:

- OAuth state validation.
- Least-privilege scopes.
- Encrypted token storage and refresh.
- Connection status/last sync visibility.
- Signature verification for webhooks.
- Event deduplication.
- Incremental sync using cursors.
- Rate-limit and retry behavior.
- Dead-letter queue for repeated failures.
- Normalized event output.
- Disconnect/revoke support.
- Access logs.

## 7.4 Normalized event schema

```json
{
  "id": "evt_123",
  "tenant_id": "tenant_456",
  "source": "hubspot",
  "event_type": "crm.contact.created",
  "occurred_at": "2026-09-07T17:00:00Z",
  "received_at": "2026-09-07T17:00:03Z",
  "entity_type": "contact",
  "entity_external_id": "hs_999",
  "payload": {
    "email": "prospect@example.com",
    "name": "Jane Smith",
    "company": "Example Co",
    "utm_campaign": "founder-demand-september"
  }
}
```

---

# 8. Startup Edition Requirements

## 8.1 Startup onboarding

Target: first active workflow in less than 45–60 minutes after authorized integrations.

```text
1. Create company workspace
2. Add company URL and product description
3. Select startup stage: pre-seed, seed, Series A
4. Select one primary goal:
   - Founder-led demand
   - Convert inbound leads to demos
   - Run a launch/campaign
   - Receive weekly growth intelligence
5. Connect HubSpot OR Pipedrive
6. Connect Gmail, Google Calendar, website form, and optional GA4
7. Define ICP in a five-minute wizard
8. Provide three to ten prior posts/emails, founder notes, or voice transcript
9. Choose default approver and safe sending policy
10. Activate one template workflow
```

Do not expose advanced policy composition, evaluation configuration, data classification, or complex agent settings during initial startup onboarding. Use safe defaults. Show advanced settings only after activation or on higher plans.

## 8.2 Startup Agentic Workflows

### Startup Workflow 1: Founder Content-to-Demand Engine

#### Problem

Founders have useful market insight but struggle to publish consistent, credible content that creates measurable demand.

#### Inputs

- Founder notes, voice transcript, product update, customer insight, or webinar/call summary.
- Startup Brand/Evidence Profile.
- ICP.
- Content goal and CTA.

#### Outputs

- LinkedIn post variants.
- Carousel outline.
- Newsletter draft.
- Product update/launch announcement.
- Short video/reel script and visual brief.
- Outbound angle or founder email draft.
- UTM-tagged CTA recommendation.

#### Workflow

```text
Founder input / approved evidence
  -> content drafts and claims check
  -> founder review/edit
  -> approve/schedule/export
  -> tracked CTA and form
  -> lead capture and attribution
  -> weekly recommendation based on results
```

#### Success metrics

- Drafts approved per week.
- Tracked link clicks.
- Campaign-attributed leads.
- Content-influenced meetings/pipeline where data exists.
- Founder time saved.

#### Safety rules

- No autonomous public posting in initial plan.
- Do not generate unsupported customer metrics or product claims.
- Clearly identify AI-assisted/generated asset status internally.

### Startup Workflow 2: Inbound Lead-to-Demo Engine

#### Problem

Startups lose high-intent leads because founders are busy and inbound qualification/follow-up is inconsistent.

#### Inputs

- Website contact/demo/waitlist form.
- CRM contact/company history.
- Lightweight ICP and disqualifier rules.
- UTM/source data.
- Calendar availability.

#### Outputs

- Priority / nurture / low-fit / needs-review classification.
- Explanation and confidence.
- CRM record create/update request.
- Lead owner routing.
- Personalized email draft.
- Scheduling link or proposed meeting times.
- Follow-up task.

#### Workflow

```text
Form/webhook event
  -> validate/deduplicate
  -> score fit and intent
  -> create/update CRM under policy
  -> notify founder/owner
  -> create approval request for email/booking message
  -> track meeting and conversion outcome
```

#### Success metrics

- First response time.
- Sales-ready/priority lead percentage.
- Demo booking rate.
- Lead-to-meeting conversion.
- CRM record completeness.

### Startup Workflow 3: Product Launch Sprint

#### Problem

Early-stage product launches, beta announcements, waitlists, webinars, and integration releases are poorly coordinated and hard to measure.

#### Inputs

- Launch name, product feature, audience, date, CTA, proof points.
- Brand/Evidence Profile.
- Available channels.
- Existing assets.

#### Outputs

- Launch brief.
- Asset checklist.
- LinkedIn posts, newsletter/email, landing-page outline, founder note, short video script.
- Campaign calendar.
- UTM links.
- Lead capture form recommendation.
- Post-launch retrospective.

#### Templates

- Beta/waitlist launch.
- New feature launch.
- Webinar/event promotion.
- Case study announcement.
- Partner/integration announcement.
- Product Hunt/supporting launch checklist.
- Hiring/culture announcement.

#### Success metrics

- Signups, demo requests, waitlist joins.
- Campaign-attributed lead volume.
- Meeting conversion.
- Asset production time.

### Startup Workflow 4: Weekly Founder Growth Brief

#### Problem

Founders lack time to analyze CRM, website, campaign, and follow-up data every week.

#### Inputs

- CRM lead/deal data.
- GA4 traffic and campaign data.
- Content/campaign activity.
- Pending lead/approval status.

#### Outputs

- Short weekly summary.
- What changed compared with prior period.
- Highest-priority leads requiring action.
- Best content/campaign sources.
- Data-quality warnings.
- Top three recommended actions.

#### Requirements

- Recommendations must link to source data.
- Keep output brief and action-oriented; do not create a long generic analytics report.
- Do not claim causation when only correlation is available.

### Startup Workflow 5: Case Study and Customer Proof Repurposer

#### Problem

Startups often have valuable customer learnings but do not convert them into trustworthy sales and marketing assets.

#### Inputs

- Customer interview notes, approved case study, implementation notes, testimonial, customer success summary.
- Permissions/approval status for naming customer and using metrics.
- Brand Profile and target ICP.

#### Outputs

- Case study outline.
- LinkedIn post(s).
- Founder story post.
- Sales one-pager draft.
- Email nurture snippet.
- Website testimonial draft.
- Outbound personalization angle.

#### Rules

- Do not use customer names, logos, quotes, or metrics without explicit tenant-provided permission status.
- Flag any unverified claim.

### Startup Workflow 6: Investor and Partnership Update Assistant (Optional, Later Startup Pack)

#### Problem

Founders repeatedly prepare investor updates, partner progress reports, and traction summaries from scattered data.

#### Inputs

- CRM metrics, product milestones, customer wins, hiring/financial metrics manually supplied by founder.
- Prior approved update format.

#### Outputs

- Weekly/monthly investor update draft.
- Partner update draft.
- Key asks and risks.
- Metrics source list.

#### Rules

- This is a drafting/summarization workflow only.
- Financial and traction claims must be linked to a source or explicitly marked as founder-provided.
- No automated email sending in initial release.

## 8.3 Startup Edition dashboard

Keep simple. Show only:

- New inbound leads.
- Priority/sales-ready leads.
- Response-time status.
- Meetings booked.
- Top campaign/content source.
- Qualified pipeline where CRM data supports it.
- Pending approvals.
- This week’s top three actions.
- Usage/quota status.

## 8.4 Startup Edition safe defaults

- One primary approver/owner.
- One CRM and one mailbox connection initially.
- External emails require approval.
- Calendar invitations require approval.
- Draft content is allowed automatically; publication requires approval.
- One active primary workflow on Founder plan; more on higher plan.
- Daily external-message and model-cost limits.
- Narrow Gmail scopes and no broad Slack ingestion by default.
- Easy disconnect, export, and deletion request path.

---

# 9. Growth Edition Requirements

## 9.1 Growth onboarding

```text
1. Create tenant and invite client team
2. Select Growth Edition and target workflows
3. Connect HubSpot, Gmail, Calendar, Slack, GA4, website form
4. Run integration/data quality assessment
5. Configure ICP, qualification/routing, owners, and approval policies
6. Build Brand/Evidence Profile and executive personas
7. Establish baseline metrics: lead volume, response time, meetings, pipeline, content cadence
8. Configure first campaign and inbound workflow
9. Run in approval-first pilot mode
10. Review weekly quality/outcome report and adjust autonomy only after evaluation
```

## 9.2 Growth Agentic Workflows

### Growth Workflow 1: Pipeline Content Operations

A governed content system that turns executive expertise and approved evidence into campaign-linked content that supports pipeline.

Includes:

- Brand/Evidence Profile Builder.
- Executive Persona Builder.
- Content Factory.
- Campaign Planner.
- Claim/evidence checking.
- Content approval and publication workflow.
- UTM and CRM attribution.
- Performance-based next-test recommendations.

### Growth Workflow 2: Lead Qualification and Routing

A configurable lead-processing workflow for multiple sales teams, segments, owners, and routing rules.

Includes:

- Advanced ICP rubric.
- Lead scoring and explanation.
- Duplicate detection.
- CRM write policy.
- Territory/segment/owner routing.
- SLA tracking and escalation.
- Approved follow-up and demo-booking workflow.
- Source-to-pipeline reporting.

### Growth Workflow 3: Account Signal and Expansion Assistant (Release 2)

Inputs:

- CRM account/deal data.
- Authorized email/context data.
- Product/support/payment signals when available.

Outputs:

- Explainable risk indicators.
- Expansion/opportunity signals.
- Recommended playbook.
- Draft CRM task and customer outreach.

Rules:

- Begin with explainable rules plus AI summarization.
- Never present a churn prediction as certainty.
- No automatic customer messages initially.

### Growth Workflow 4: Marketing-to-Sales SLA Monitor

Problem: marketing and sales disagree about lead quality and response ownership.

Inputs:

- Lead creation time.
- Lead routing and owner.
- Sales action timestamps.
- Qualification feedback.

Outputs:

- SLA breach alerts.
- Unworked priority lead queue.
- Rejection reason analysis.
- Weekly routing/quality report.
- Recommended rubric/process changes.

Success metrics:

- Speed-to-lead.
- Sales-accepted-lead rate.
- Lead follow-up compliance.
- Reason-coded lead rejection patterns.

### Growth Workflow 5: Account-Based Campaign Coordinator (Release 2)

Problem: teams want coordinated content/outreach for target accounts but cannot manually manage account lists, content variants, and follow-up tasks.

Inputs:

- Approved target account list.
- ICP/account attributes.
- Campaign objective.
- Approved content/evidence assets.

Outputs:

- Account segmentation.
- Campaign and content plan.
- Personalized but approval-controlled draft messages/assets.
- CRM tasks and engagement reporting.

Rules:

- Do not auto-send mass personalized outreach in initial release.
- Follow all tenant policies and send caps.

### Growth Workflow 6: Finance/Operations Pack (Release 3, not MVP)

Later workflows:

- AR aging monitor.
- Finance-approved collections reminder drafting.
- Executive performance report.
- Operational playbook coordinator.

Finance actions require separate requirements, security review, finance approver roles, and strict approval policies before development.

---

# 10. Shared Agent Specifications

## 10.1 Agent A: Brand and Evidence Profile Builder

### Purpose

Create a versioned, approved source of truth for brand voice, audience, evidence, product claims, restrictions, and executive persona context.

### Inputs

- Approved website content.
- Brand guide.
- Product collateral.
- Case studies/testimonials with permissions.
- Past approved posts/emails/newsletters.
- ICP definition.
- Prohibited claims/topics.
- Founder or executive notes.

### Outputs

- Brand voice and tone guide.
- ICP summary.
- Messaging pillars.
- Claim library with evidence references.
- Prohibited/restricted claim list.
- Executive persona profile(s).
- Data gaps/confidence.

### Acceptance criteria

- User can create, edit, approve, and version profiles.
- Downstream content references the profile version used.
- Specific claims link to evidence or are flagged as unsupported.

## 10.2 Agent B: Pipeline Content Factory

### Purpose

Create credible, on-brand, reviewable content tied to a target audience, conversion path, and campaign.

### Inputs

- Approved brand/evidence and persona profiles.
- Brief, goal, audience, CTA, channel, source material.
- Campaign context and performance data if available.

### Outputs

- Content drafts in approved formats.
- Alternative hooks/angles.
- UTM CTA recommendation.
- Claim/evidence references.
- Compliance/provenance flags.
- Suggested campaign assignment.

### Supported initial formats

- LinkedIn posts.
- Carousel outlines.
- Newsletter drafts.
- Blog outlines.
- Product-launch announcements.
- Short-video/reel scripts and visual briefs.
- Outreach angles.

### Rules

- Content can be generated automatically but publication requires policy approval.
- No unsupported metrics, testimonials, or customer claims.
- Store asset provenance: human authored, AI assisted, AI generated, human edited.

## 10.3 Agent C: Campaign Planner and Attribution Coordinator

### Purpose

Turn an objective into an organized campaign plan with content, CTA, tracked links, approval tasks, and measurable results.

### Inputs

- Objective, ICP, dates, channels, CTA, assets, optional budget.

### Outputs

- Campaign brief.
- Content calendar.
- Asset checklist.
- UTM plan.
- Conversion/lead capture recommendation.
- Weekly performance analysis.
- Next-test recommendations.

### Rules

- No autonomous paid-ad spending or budget changes.
- Report sourced and influenced pipeline separately.
- Display attribution gaps/caveats.

## 10.4 Agent D: Lead Qualification and Routing Agent

### Purpose

Validate, score, route, and create controlled next actions for inbound leads.

### Inputs

- Form/webhook lead data.
- CRM history.
- ICP/rubric.
- UTM/source/campaign data.
- Routing rules.

### Output schema

```json
{
  "lead_id": "lead_123",
  "overall_score": 82,
  "classification": "sales_ready",
  "confidence": 0.88,
  "score_breakdown": {
    "fit": 34,
    "intent": 28,
    "need": 14,
    "data_quality": 6
  },
  "reasons": [
    "Company matches target segment",
    "Requested a demo",
    "Campaign source is high-intent"
  ],
  "missing_information": [
    "Implementation timeline not supplied"
  ],
  "recommended_next_action": "Assign to owner and generate a scheduling email draft",
  "policy_result": "CRM_WRITE_ALLOWED_EMAIL_APPROVAL_REQUIRED"
}
```

### Rules

- Never delete records automatically.
- No bulk CRM updates in initial release.
- External email requires approval initially.
- Classification must be explainable and editable by users.
- Low data quality must result in `needs_review` when appropriate.

## 10.5 Agent E: Demo Booking Assistant

### Purpose

Help a qualified lead move to a meeting while preserving calendar privacy and approval requirements.

### Inputs

- Qualified lead.
- Owner/routing rules.
- Meeting type/duration.
- Calendar free/busy availability.
- Time zone.

### Outputs

- Recommended meeting owner.
- Available slots.
- Draft email/scheduling message.
- Draft calendar event.
- Reminder/follow-up task.

### Rules

- Read free/busy only, not unrelated event details.
- Email/invitation requires approval in initial release.

## 10.6 Agent F: Weekly Growth Brief Agent

### Purpose

Summarize weekly GTM movement and recommend a short set of evidence-based actions.

### Inputs

- CRM leads/deals.
- Campaign/content activity.
- GA4/UTM results.
- Pending actions/approvals.
- Data quality status.

### Outputs

- Key changes since prior week.
- Best and weakest acquisition sources.
- Priority lead/account action list.
- Top content/campaign insight.
- Data quality warnings.
- Three recommended actions.

### Rules

- All recommendations link to data references.
- State uncertainty and do not overstate causal claims.

## 10.7 Agent G: Account Signals Agent (Growth Release 2)

### Purpose

Detect explainable expansion or risk indicators in accounts and create reviewable next actions.

### Inputs

- CRM, email context, support/product/payment signals where authorized.

### Outputs

- Account health trend.
- Evidence-backed signal summary.
- Recommended playbook.
- CRM task and outreach draft.

---

# 11. Workflow Runtime Requirements

## 11.1 State machine

```text
DRAFT
  -> CONFIGURED
  -> READY
  -> RUNNING
  -> WAITING_FOR_DATA
  -> WAITING_FOR_APPROVAL
  -> EXECUTING_ACTION
  -> COMPLETED
  -> FAILED
  -> CANCELLED
```

## 11.2 Required workflow features

- Manual, schedule, and webhook triggers.
- JSON-schema input/output validation.
- Step-level state/status.
- Retry/timeouts/dead-letter queue.
- Idempotency.
- Policy checkpoints.
- Approval gates.
- Pause/cancel/retry.
- Human takeover.
- Source/evidence tracking.
- Cost tracking.

## 11.3 Example: inbound lead to demo

```text
1. Receive verified website form event
2. Validate and deduplicate
3. Retrieve allowed CRM context
4. Assess data quality
5. Run Lead Qualification Agent
6. Validate output schema
7. Apply policy
8. Create/update CRM record only when allowed
9. Route to owner and notify internally
10. Create follow-up/booking approval request
11. Store attribution and evidence records
12. Update dashboard and weekly brief inputs
```

## 11.4 Example: founder content to demand

```text
1. Founder submits note, voice transcript, product update, or source material
2. Load approved Brand/Evidence Profile
3. Generate content asset variants
4. Validate/flag claims and evidence
5. User edits and submits selected asset for approval
6. Publish through supported official integration or export for manual posting
7. Attach UTM CTA and campaign ID
8. Ingest campaign/website/CRM events
9. Report traffic/leads/meetings/pipeline with attribution caveats
```

---

# 12. Data Model

| Entity | Key fields | Purpose |
|---|---|---|
| Tenant | id, edition, plan, name, settings | Customer workspace |
| User | id, tenant_id, role, status | Product user |
| IntegrationConnection | id, tenant_id, provider, scopes, credential_ref, health | Connected provider account |
| AgentDefinition | id, tenant_id, edition, owner, lifecycle, policy_id, cost_budget | Agent Registry record |
| AgentVersion | id, agent_id, version, model, prompt_ref, evaluation_id | Versioned implementation |
| Policy | id, tenant_id, rules, version, active | Permission/approval rules |
| WorkflowDefinition | id, tenant_id, template_id, steps, trigger, policy_id | Workflow blueprint |
| WorkflowRun | id, tenant_id, workflow_id, status, input, cost, timestamps | Workflow execution |
| ApprovalRequest | id, tenant_id, action, target, payload, status | Approval record |
| ActionExecution | id, tenant_id, provider, request, response, status | External action result |
| EvidenceRecord | id, tenant_id, run_id, agent_version_id, payload_ref | Immutable/replayable evidence |
| EvaluationSuite | id, agent_type, cases, thresholds | Agent quality test set |
| EvaluationRun | id, agent_version_id, metrics, passed | Evaluation outcome |
| BrandProfile | id, tenant_id, version, voice, claims, restrictions | Brand/evidence source of truth |
| PersonaProfile | id, tenant_id, identity, voice, examples, approved | Founder/executive context |
| ContentAsset | id, tenant_id, type, status, content, provenance, campaign_id | Content lifecycle record |
| Campaign | id, tenant_id, template, objective, audience, dates | Campaign organization |
| Lead | id, tenant_id, source, score, status, owner, external_id | Inbound/qualified lead |
| AttributionEvent | id, tenant_id, content_id, campaign_id, lead_id, event | Conversion chain record |
| DataQualityIssue | id, tenant_id, severity, entity, reason, status | Quality/control record |
| CostRecord | id, tenant_id, run_id, provider, units, cost | Usage/cost record |
| AuditLog | id, tenant_id, actor, event, entity, metadata | Security and activity history |

All records containing customer data must include `tenant_id` and be protected by Row-Level Security.

---

# 13. User Experience Requirements

## 13.1 Shared navigation

```text
Home
Pipeline
Content Studio
Campaigns
Leads
Approvals
Automations / Agents
Workflows
Analytics
Integrations
Data Quality
Knowledge & Brand
Settings
```

## 13.2 Startup Edition UX

Use simpler labels and progressive disclosure:

| Technical concept | Startup Edition label |
|---|---|
| Agent Registry | Automations |
| Policy Engine | Automation Rules |
| Evaluation Console | Automation Quality (hidden initially) |
| Evidence Ledger | Activity History |
| Workflow Runtime | Workflow Runs (minimal detail) |

Startup home screen should focus on:

- Leads needing response.
- Meetings booked.
- This week’s content/campaign performance.
- Pending approvals.
- Weekly Growth Brief.
- Usage/quota status.

## 13.3 Growth Edition UX

Show full operational controls:

- Executive pipeline dashboard.
- Lead routing and SLA view.
- Content/campaign workflow view.
- Approval center.
- Agent Registry with permissions/status/evaluation/cost.
- Workflow traces and errors.
- Data Quality Center.
- Attribution methodology and pipeline reporting.

## 13.4 Required screen list

| Screen | Release requirement |
|---|---|
| Login/tenant selection | P0 |
| Onboarding wizard with edition selection | P0 |
| Home dashboard (edition-specific) | P0 |
| Integrations | P0 |
| Knowledge & Brand | P0 |
| Content Studio | P0 |
| Campaign planner | P0 |
| Leads and routing queue | P0 |
| Approvals | P0 |
| Automations/Agent Registry | P0 |
| Workflow runs | P0 |
| Data Quality | P0 |
| Analytics/attribution | P0 |
| Settings, roles, policies, quotas | P0 |

---

# 14. Analytics and Attribution

## 14.1 Reporting principles

- Do not promise perfect attribution.
- Clearly distinguish sourced pipeline from influenced pipeline.
- Show first-touch and last-touch attribution initially.
- Show missing data and untracked events.
- Link recommendations to evidence.

## 14.2 Required metrics

### Startup Edition

- New inbound leads.
- Priority/sales-ready leads.
- Lead response time.
- Meetings booked.
- Campaign/content-linked visits and leads.
- Top source/content asset.
- Qualified pipeline where CRM data permits.
- Pending approvals.
- Usage/quota status.

### Growth Edition

- Lead volume, qualification, owner routing, and SLA adherence.
- Sales-accepted leads.
- Meetings and opportunity conversion.
- Sourced/influenced pipeline.
- Content/campaign performance linked to lead/opportunity data.
- Agent quality/override rate.
- Workflow completion/failure/retry rate.
- Connector freshness/health.
- Cost per workflow, qualified lead, and meeting.

## 14.3 UTM requirements

Every campaign content asset with a CTA must support standardized UTM generation:

```text
utm_source
utm_medium
utm_campaign
utm_content
utm_term (optional)
```

Store UTM context on attribution events and, where allowed, synchronized CRM records.

---

# 15. Security, Privacy, and AI Safety

## 15.1 Security baseline

- Encryption in transit and at rest.
- KMS-backed secrets management.
- Least-privilege OAuth scopes.
- No secrets in logs, source code, frontend storage, or error reports.
- Postgres Row-Level Security.
- Webhook signature verification and replay prevention.
- Rate limits and abuse protection.
- File validation/malware scanning.
- Dependency and secret scanning in CI.
- Backups and restoration testing.
- Audit logs for sensitive events.

## 15.2 Agent safety baseline

- Treat CRM text, emails, web pages, uploaded docs, and form responses as untrusted input.
- Never allow retrieved content to change system policy or tool permissions.
- Use explicit action/tool allowlists.
- Validate outputs against schemas.
- Enforce per-tenant quotas, send caps, and cost budgets.
- Support kill switches: global, tenant, integration, workflow, campaign, agent.
- Require human review for important external actions at launch.
- Maintain fallback/manual paths for all customer-critical workflows.

## 15.3 Content provenance

Each content asset must record:

- Human-authored, AI-assisted, AI-generated, or human-edited-after-AI status.
- Brand/Evidence Profile version.
- Source evidence references for specific claims.
- Reviewer/approver.
- Publication/scheduling event.
- Optional disclosure/metadata field.

## 15.4 Privacy

- Customer can disconnect integrations.
- Customer can request data export/deletion subject to legal/contractual retention rules.
- Client data cannot train shared models without explicit opt-in and legal/privacy review.
- Any aggregated benchmark product requires a separate consent and privacy design.

---

# 16. Pricing and Packaging

Pricing should be simple to understand, predictable enough for startups, and economically sustainable for variable AI costs.

## 16.1 Recommended packaging model

All paid plans contain:

1. A platform fee.
2. Included workflow capacity/usage.
3. Clear quotas for expensive usage.
4. Optional implementation or managed-service add-ons.

Avoid “unlimited AI,” “unlimited videos,” or vague outcome guarantees.

## 16.2 Startup Edition pricing

### Option A: Startup Program (recommended launch packaging)

Offer a structured startup program for venture-backed/accelerator/community startups. It creates a strong acquisition channel without permanently discounting every customer.

| Plan | List price | Startup Program price | Best for | Includes |
|---|---:|---:|---|---|
| Trial | $0 | $0 | Evaluation | 7–14 days, one template workflow, limited credits, no autonomous sending |
| Founder | $99/month | $49/month for eligible startups for first 12 months | Pre-seed/seed founder-led GTM | One user/owner, one CRM, Founder Content or Inbound Lead workflow, low usage limits |
| Startup Growth | $299/month | $149/month for eligible startups for first 12 months | Seed/Series A teams | Up to 5 users, multiple templates, campaigns, lead routing, weekly growth brief, higher quotas |
| Startup Scale | $599/month | $399/month for eligible startups for first 12 months | Larger Series A / high-growth startup | More users, advanced routing, higher limits, priority support, selected Growth controls |

### Eligibility for Startup Program

Require at least one of:

- Incorporated less than 5 years ago.
- Fewer than 50 employees.
- Below $5M annual revenue.
- Member of a recognized accelerator, incubator, VC portfolio, university startup program, or partner ecosystem.

The discount should expire after 12 months or once the company surpasses the threshold, then transition the customer to standard Startup Scale or Growth Edition pricing. This avoids permanent underpricing while rewarding early adoption.

### Startup usage limits

Do not make features “unlimited.” Configure limits by plan for:

- Active workflow templates.
- Number of users.
- Monthly lead processing events.
- AI content generations.
- Connected inboxes/CRMs.
- Video/media generation credits.
- Enrichment calls.
- External action/send caps.
- Data retention/export volume.

### Startup managed add-ons

| Add-on | Indicative price | Scope |
|---|---:|---|
| Founder Growth Setup | $500–$1,000 one-time | Integration setup, basic Brand/Evidence Profile, ICP rubric, first workflow |
| Launch Sprint Setup | $750–$1,500 one-time | Campaign brief, assets, tracking, launch workflow configuration |
| Monthly Growth Office Hours | $250–$500/month | Strategy, workflow reviews, content/campaign optimization |

## 16.3 Growth Edition pricing

| Plan | Indicative price | Includes |
|---|---:|---|
| Growth Core | $750/month | Core pipeline workflow, team access, HubSpot/Gmail/Calendar/GA4, approvals, attribution, governance controls |
| Growth Pro | $1,500–$2,500/month | Multiple workflows, advanced routing, campaigns, full control plane, higher quotas, priority support |
| Managed Growth Operations | $3,000–$8,000+/month | Software plus implementation, monitoring, content/campaign operations, optimization, reporting |
| Enterprise/Custom | Custom | SSO, advanced security, custom connectors, custom policies, contractual requirements |

Growth pricing should be validated with design partners and should not be positioned as a replacement for every existing tool. It is a governed automation and outcomes layer.

## 16.4 Engineering requirements for pricing

- Tenant edition, plan, and eligibility status.
- Feature flags.
- Usage metering by workflow, model, connector, and action type.
- Cost budgets and overage behavior.
- Startup Program discount expiry date and automatic transition notifications.
- Admin ability to issue credits or pilot overrides.
- Invoice/subscription integration later; manual billing acceptable for first pilots.

---

# 17. Development Roadmap

## Phase 0: Customer validation (before broad build)

### Founder actions

- Interview 15–20 startup founders and 10–15 growth-company buyers.
- Validate three startup workflows: Founder Content-to-Demand, Inbound Lead-to-Demo, Product Launch Sprint.
- Validate two growth workflows: Pipeline Content Operations, Lead Qualification/Routing.
- Secure 3–5 paid design partners across the two editions.
- Collect baseline metrics and real workflow artifacts: forms, CRM views, emails, content, campaign calendars, reports.

### Go criteria for Startup Edition expansion

- At least 3 paid startup pilots use the same core workflow.
- Setup can be completed in under one hour excluding third-party OAuth approvals.
- At least 60% weekly active usage by week four.
- At least 2 pilots agree to continue on paid plan.
- Workflow improves response time, qualified lead rate, meeting conversion, or content-to-lead activity.

## Phase 1: Shared foundation (Weeks 1–4)

- Monorepo, CI/CD, staging/production environments.
- Tenant/user/role schema and Row-Level Security.
- Auth/invitations.
- Audit logs.
- Connector/OAuth framework.
- Agent Registry base.
- Policy Engine base.
- Approval Center base.
- Evidence Ledger base.
- Plan/feature-flag/usage ledger base.

## Phase 2: Core integrations and lead workflow (Weeks 5–8)

- HubSpot connector.
- Pipedrive connector if team capacity permits; otherwise simulate/plan after HubSpot works.
- Gmail connector.
- Google Calendar free/busy connector.
- Website webhook intake.
- GA4 ingestion.
- Lead data model, rubric, Lead Qualification Agent, CRM routing, approvals.
- Data Quality Center.
- Workflow Run UI and kill/pause controls.

## Phase 3: Content and startup templates (Weeks 9–12)

- Brand/Evidence Profile Builder.
- Content Studio and Pipeline Content Factory.
- Campaign calendar and UTM builder.
- Startup Edition onboarding.
- Founder Content-to-Demand template.
- Product Launch Sprint template.
- Weekly Founder Growth Brief.
- Basic Startup and Growth dashboards.

## Phase 4: Pilot hardening (Weeks 13–16)

- Evaluation Console and labeled evaluation data.
- Security/permission/isolation testing.
- Cost budget and quota enforcement.
- Full end-to-end workflow tests.
- Documentation, demo data, error handling, monitoring.
- Launch paid design-partner pilots in approval-first mode.

## Phase 5: Post-PMF expansion

Only after pilot usage/retention validates the first workflows:

- Demo Booking Assistant improvements.
- LinkedIn/social integration expansion.
- Account Signal Agent.
- Marketing-to-Sales SLA Monitor.
- Account-based campaign coordinator.
- Managed-service operational tooling.
- Finance/Operations Pack requirements and separate implementation plan.

---

# 18. Suggested Intern Team Assignments

| Team | Scope | Key deliverables |
|---|---|---|
| Team A: Core Platform | Auth, tenants, RBAC, RLS, audit logs, plans, usage | Secure multi-tenant foundation |
| Team B: Integrations | OAuth, HubSpot, Gmail, Calendar, webhooks, GA4, health checks | Connector Trust Layer |
| Team C: Control Plane | Agent Registry, policies, approvals, evidence, kill switch | Governed actions and observability |
| Team D: Workflow/AI | Lead scoring, brand/evidence, content, weekly brief, evaluations | Structured and safe AI workflows |
| Team E: Frontend | Startup onboarding, Growth onboarding, dashboards, leads, content, approvals | Edition-specific UI over shared backend |
| Team F: Analytics/QA/DevOps | UTMs, attribution, dashboards, testing, CI/CD, monitoring | Reliable reporting and release quality |

---

# 19. Definition of Done: Pilot MVP

## 19.1 Shared platform

- [ ] Customer can create tenant and invite users.
- [ ] Tenant isolation is enforced in UI, API, database, queue jobs, documents, and retrieval.
- [ ] All critical actions are audit logged.
- [ ] OAuth credentials are encrypted and never exposed in logs.
- [ ] Plan/edition flags and quotas work.

## 19.2 Startup Edition

- [ ] Founder can onboard in under 60 minutes with a supported CRM, Gmail, Calendar, website form, and basic brand inputs.
- [ ] Founder can activate Founder Content-to-Demand or Inbound Lead-to-Demo template.
- [ ] Content can be generated, edited, approved, exported/scheduled, and attributed through tracked links.
- [ ] Website inbound lead can be scored, routed, and written to CRM according to policy.
- [ ] External email/calendar action requires approval.
- [ ] Weekly Growth Brief produces source-linked recommendations.
- [ ] Dashboard displays core startup metrics and usage status.

## 19.3 Growth Edition

- [ ] Growth team can configure lead rubric, routing, policies, approvers, and SLAs.
- [ ] Growth team can inspect Agent Registry, policy decisions, evidence records, workflow runs, data-quality issues, and costs.
- [ ] Campaigns generate UTM plans and show first/last-touch plus sourced/influenced pipeline where data permits.
- [ ] Growth team can pause any agent/workflow/integration.

## 19.4 Quality and security

- [ ] Minimum evaluation set: 50 labeled lead cases, 20 content/brand cases, 20 claim-evidence cases, 20 prompt-injection/safety cases.
- [ ] Core business logic has unit tests; connectors have integration tests/mocks; full end-to-end tests exist.
- [ ] No cross-tenant access test passes.
- [ ] Webhook verification, retries, idempotency, and failure visibility work.
- [ ] External action is never reported as complete until provider response confirms it.

---

# 20. Key Metrics

## Startup Edition metrics

- Activation: time to first live workflow.
- Weekly active founders/teams.
- Content draft approval rate.
- New inbound and priority lead count.
- First response time.
- Lead-to-meeting conversion.
- Campaign/content-attributed leads.
- Upgrade/retention after pilot or Startup Program period.
- Cost per active startup tenant.

## Growth Edition metrics

- Qualified/sales-accepted lead rate.
- Speed-to-lead and routing SLA adherence.
- Meetings and opportunity creation.
- Sourced and influenced pipeline.
- Content/campaign contribution.
- Workflow completion/failure/override rate.
- Approval turnaround time.
- Data freshness and connector health.
- Cost per qualified lead and gross margin per tenant.

## Shared product metrics

- Agent evaluation quality.
- Policy block/approval rate.
- Unsupported claim rate.
- CRM write accuracy.
- Connector error rate.
- External action failure rate.
- Cost by agent/workflow/tenant.

---

# 21. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Startup segment causes distraction and low-ARPU support burden | Keep Startup Edition template-led, self-serve, quota-limited, and built on shared core only |
| Building two separate products | Use edition flags, templates, feature flags, and progressive UI—not separate codebases |
| Generic content market is saturated | Tie content to approved evidence, conversion assets, CRM, and pipeline attribution |
| Startups build tools internally | Win on speed, templates, integrations, governance, attribution, and managed expertise—not generic chat |
| Low-quality data causes bad decisions | Data Quality Center, confidence labels, review state, safe defaults |
| Social API restrictions | Use official API paths where available; retain manual export/scheduling fallback |
| Unreviewed AI causes reputation damage | Approval-first external actions, claim checks, evidence references, send caps |
| Cross-tenant leak | RLS, tenant-scoped jobs/retrieval, permission tests, credential isolation |
| Variable model costs erase margin | Metering, quotas, budget alerts, model routing, no unlimited promises |
| Discount program attracts non-paying users | Eligibility checks, time-bound discount, clear conversion pricing, paid pilots |

---

# 22. Founder Decisions Required Before Implementation

1. Confirm initial vertical: B2B SaaS only, or B2B SaaS plus tech-enabled services.
2. Identify 3–5 paid design partners: ideally 2 startup and 2 growth customers.
3. Confirm initial CRM priority: HubSpot only for first MVP, or HubSpot + Pipedrive with added development time.
4. Confirm exact definition of a qualified/sales-accepted lead for each pilot.
5. Confirm startup program eligibility rules and discount duration.
6. Confirm which Startup Edition templates launch first. Recommended: Founder Content-to-Demand, Inbound Lead-to-Demo, Product Launch Sprint, Weekly Growth Brief.
7. Confirm which external actions remain approval-only in pilot. Recommended: all external messages, invitations, publishing.
8. Obtain legal review for terms, privacy, DPA, data retention, AI-content disclosures, and customer-content permissions.
9. Set customer baseline metrics before turning on workflows.
10. Decide managed-service boundaries: what agency operators do manually versus what platform agents do.

---

# Appendix A: Common API Surface

```text
# Identity / tenant
GET    /api/v1/me
GET    /api/v1/tenant
POST   /api/v1/tenant/invitations
PATCH  /api/v1/users/{id}/role

# Edition / plan / quota
GET    /api/v1/billing/plan
GET    /api/v1/usage
POST   /api/v1/admin/credits

# Integrations
GET    /api/v1/integrations
POST   /api/v1/integrations/{provider}/connect
POST   /api/v1/integrations/{connection_id}/disconnect
POST   /api/v1/webhooks/{provider}

# Brand / knowledge
GET    /api/v1/brand-profiles
POST   /api/v1/brand-profiles
PATCH  /api/v1/brand-profiles/{id}
POST   /api/v1/brand-profiles/{id}/approve
POST   /api/v1/evidence/upload

# Content / campaigns
POST   /api/v1/content/generate
GET    /api/v1/content-assets
PATCH  /api/v1/content-assets/{id}
POST   /api/v1/content-assets/{id}/submit-approval
POST   /api/v1/campaigns
POST   /api/v1/campaigns/{id}/generate-plan

# Leads / workflows
GET    /api/v1/leads
GET    /api/v1/leads/{id}
POST   /api/v1/leads/{id}/rescore
POST   /api/v1/leads/{id}/push-to-crm
GET    /api/v1/workflow-runs
POST   /api/v1/workflow-runs/{id}/retry
POST   /api/v1/workflow-runs/{id}/cancel

# Control plane
GET    /api/v1/agents
POST   /api/v1/agents
POST   /api/v1/agents/{id}/pause
POST   /api/v1/agents/{id}/resume
GET    /api/v1/policies
POST   /api/v1/policies
GET    /api/v1/approvals
POST   /api/v1/approvals/{id}/approve
POST   /api/v1/approvals/{id}/reject
GET    /api/v1/evidence/{workflow_run_id}
GET    /api/v1/evaluations
POST   /api/v1/evaluations/run

# Reporting
GET    /api/v1/dashboard
GET    /api/v1/analytics/pipeline
GET    /api/v1/analytics/attribution
GET    /api/v1/data-quality
```

---

# Appendix B: Agent Promotion Checklist

Before an agent becomes active, gains a new action permission, or changes from approval-required to limited autonomous:

- [ ] Named human owner exists.
- [ ] Specific business outcome is documented.
- [ ] Input data sources and classification are approved.
- [ ] Tool/action allowlist is defined.
- [ ] Policy/approval rules are defined.
- [ ] Evaluation dataset exists.
- [ ] Quality and safety thresholds are met.
- [ ] Cost budget is configured.
- [ ] Failure and escalation behavior is tested.
- [ ] Kill switch is tested.
- [ ] Evidence logging is verified.
- [ ] Rollback plan is tested.

---

# Appendix C: Intern Development Rules

1. Build shared platform services once; use editions, templates, feature flags, and progressive UI to serve different segments.
2. Do not build a generic agent builder before core workflows are proven with paid customers.
3. Do not add an integration unless it supports a named workflow and design partner need.
4. Do not allow LLM output or retrieved content to change system policies, credentials, or tool permissions.
5. Do not treat an external action as complete until the provider confirms it.
6. Do not hide failed syncs, missing data, uncertainty, or workflow errors.
7. Keep startup flows opinionated and fast; keep growth flows configurable and governable.
8. Keep external communication approval-first in pilots.
9. Use typed schemas, test fixtures, and versioned prompts for every agent workflow.
10. Demonstrate an end-to-end working workflow every week using safe test or pilot data.

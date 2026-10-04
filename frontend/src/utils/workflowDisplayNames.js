// Utility to provide concise human‑readable workflow names

const DISPLAY_NAME_MAP = {
  email_summarizer: 'Email Summarizer',
  product_launch: 'Product Launch Sprint',
  product_launch_sprint: 'Product Launch Sprint',
  meeting_intelligence_followup: 'Meeting Intelligence & Follow-up',
  meeting_intelligence: 'Meeting Intelligence & Follow-up',
  account_signal_expansion: 'Account Signals',
  billing_agent: 'Billing Agent',
  case_brief_summarization: 'Case Summarizer',
  founder_content_to_demand: 'Content Generator',
  account_based_campaign_coordinator: 'Campaign Coordinator',
  ai_account_manager: 'Account Manager',
  campaign_orchestrator: 'Campaign Orchestrator',
  case_study_repurposer: 'Case Study Repurposer',
  compliance_monitor: 'Compliance Monitor',
  content_factory: 'Content Factory',
  coordinator_communication_copilot: 'Communication Copilot',
  document_intake_extraction: 'Document Intake',
  freshness_publishing_review: 'Publishing Review',
  inbound_lead_to_demo: 'Lead to Demo',
  journey_task_orchestration: 'Journey Operations',
  lead_qualification_routing: 'Lead Qualification',
  lead_qualifier: 'Lead Qualifier',
  marketing_to_sales_sla_monitor: 'Marketing SLA Monitor',
  ops_playbook: 'Operations Playbook',
  patient_intake_triage: 'Patient Intake',
  provider_evidence_verification: 'Provider Verification',
  quote_normalization_comparison: 'Quote Comparison',
  finance_expense_monitoring: 'Expense Monitoring',
  retail_inventory_health_monitor: 'Inventory Monitor',
  saas_churn_prevention: 'Churn Prevention',
  saas_pipeline_velocity: 'Pipeline Velocity',
  social_campaign: 'Social Campaign',
  tenant_flight_risk: 'Account Risk Monitor',
  weekly_founder_growth_brief: 'Founder Growth Brief',
}

function humanize(key) {
  return key
    .split('_')
    .filter(Boolean)
    .map(w => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ')
}

export function getDisplayName(key, backendName) {
  if (!key) return ''
  if (DISPLAY_NAME_MAP[key]) return DISPLAY_NAME_MAP[key]
  // If the backend already supplies a display name, use it (covers any custom names not in the map)
  if (backendName && backendName.trim()) return backendName.trim()
  // Fallback: generate a readable name from the key
  return humanize(key)
}

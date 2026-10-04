# Medical Tourism Pilot #1 Specification

## 1. Vertical Overview
Medical Tourism (International Patient Care Coordination for Fertility/IVF and Revision Orthopedics in India) is **Vertical Pilot #1** built on the reusable SMBFlow core.

## 2. Representative Workflow Flow
```text
New Patient Inquiry ──► Intake Triage ──► Document Intake & Extraction ──► Human Review ──► Quote Normalization & Comparison ──► Case Brief ──► Communication Draft ──► Human Approval ──► Patient Journey
```

## 3. Non-Clinical Safety Guardrails
- **No Diagnosis**: System does not interpret images or diagnose conditions.
- **No Prescription**: System does not suggest medications or dosages.
- **No Clinical Recommendation**: System does not recommend clinical treatment or rank hospitals clinically.
- **No Unapproved External Communications**: All outgoing patient-facing messages require explicit coordinator approval.
- **Confidential Document Isolation**: Patient medical records are strictly protected and never rendered on public surfaces.

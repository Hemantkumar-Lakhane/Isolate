"""
db/seed/email_seed.py
=====================
Generates realistic synthetic email dataset for workflow execution testing.

Produces:
  - 40 synthetic business emails covering 20 realistic operational scenarios
  - Deterministic random generation using random.seed(42)
  - Metadata: data_origin="synthetic", is_test_data=True, dataset="email_workflow_demo"

Usage:
  python db/seed/email_seed.py
Output:
  db/seed/data/email_messages.json
"""

import json
import random
from datetime import datetime, timedelta
from pathlib import Path

random.seed(42)

SEED_DIR = Path("db/seed/data")

SCENARIOS = [
    {
        "scenario": "customer_support_request",
        "priority": "normal",
        "labels": ["INBOX", "SUPPORT"],
        "subjects": ["Help with login issue on user dashboard", "Cannot access reporting exports"],
        "senders": ["alice.smith@clientcorp.example.test", "support.user@acmelabs.example.test"],
        "recipients": ["support@smbflow.test"],
        "bodies": [
            "Hi team, I am unable to log in to our dashboard after the latest update. Could someone help reset my session?",
            "Hello, our weekly export script is failing with error 403. Please assist when possible."
        ]
    },
    {
        "scenario": "customer_complaint",
        "priority": "high",
        "labels": ["INBOX", "COMPLAINT"],
        "subjects": ["Unacceptable downtime during peak hours", "Order processing delay for Account #9482"],
        "senders": ["derek.vance@enterpriseco.example.test", "ops.head@globalretail.example.test"],
        "recipients": ["support@smbflow.test", "escalations@smbflow.test"],
        "bodies": [
            "Our team experienced 45 minutes of complete service interruption today during business hours. We need an explanation and SLA credit.",
            "Order #9482 has been stuck in 'Processing' for 3 days. Our customer is threatening cancellation."
        ]
    },
    {
        "scenario": "customer_escalation",
        "priority": "urgent",
        "labels": ["INBOX", "URGENT", "ESCALATION"],
        "subjects": ["URGENT: System outage affecting 500+ active users", "CRITICAL: Data sync failure across region east"],
        "senders": ["cto@majorclient.example.test", "vp.engineering@techcorp.example.test"],
        "recipients": ["escalations@smbflow.test", "oncall@smbflow.test"],
        "bodies": [
            "CRITICAL ALERT: All API requests for account MC-902 are failing with 500 errors. 500+ active users blocked!",
            "Data sync between primary database and workspace instances has halted. Executive attention required immediately."
        ]
    },
    {
        "scenario": "invoice_payment_issue",
        "priority": "high",
        "labels": ["INBOX", "FINANCE"],
        "subjects": ["Discrepancy on Invoice #INV-4821", "Payment status for Purchase Order #PO-9912"],
        "senders": ["billing@vendorco.example.test", "accounts@partnernet.example.test"],
        "recipients": ["finance@smbflow.test"],
        "bodies": [
            "Invoice #INV-4821 shows a charge of $4,500, but our contracted rate was $3,800. Please issue a corrected invoice.",
            "We have not received payment for PO-9912 which was due on Sept 1st. Please update payment status."
        ]
    },
    {
        "scenario": "payment_reminder",
        "priority": "normal",
        "labels": ["INBOX", "FINANCE"],
        "subjects": ["Friendly Reminder: Upcoming Renewal Invoice #INV-5012", "Scheduled Payment Notification"],
        "senders": ["billing-system@smbflow.test", "ar@serviceprovider.example.test"],
        "recipients": ["finance@smbflow.test"],
        "bodies": [
            "This is a automated reminder that subscription invoice #INV-5012 ($1,200) is scheduled for auto-debit in 5 days.",
            "Your monthly platform statement for August 2026 is now available for download."
        ]
    },
    {
        "scenario": "new_customer_inquiry",
        "priority": "normal",
        "labels": ["INBOX", "SALES"],
        "subjects": ["Inquiry regarding Enterprise Plan features", "Demo request for workflow automation"],
        "senders": ["leads@prospectcorp.example.test", "innovation@healthsys.example.test"],
        "recipients": ["sales@smbflow.test"],
        "bodies": [
            "We are evaluating workflow automation platforms for our team of 40 users. Does SMBFlow support HIPAA compliance?",
            "Hi, we would like to schedule a 30-minute product demo for our operations leadership team next week."
        ]
    },
    {
        "scenario": "sales_lead",
        "priority": "high",
        "labels": ["INBOX", "SALES"],
        "subjects": ["RFP Submission Request — Operations Platform", "Expansion Opportunity for Account #SAAS-401"],
        "senders": ["procurement@bigcorp.example.test", "csm@smbflow.test"],
        "recipients": ["sales@smbflow.test"],
        "bodies": [
            "BigCorp is issuing an RFP for an AI orchestration layer. Submissions due by Sept 20. Please find details attached.",
            "Account SAAS-401 has requested 100 additional seat licenses starting next quarter. Estimated deal size $50k ARR."
        ]
    },
    {
        "scenario": "meeting_request",
        "priority": "normal",
        "labels": ["INBOX", "CALENDAR"],
        "subjects": ["Scheduling: Q3 Quarterly Business Review", "Sync on Product Roadmap integration"],
        "senders": ["sarah.csm@smbflow.test", "pm.lead@integrationpartner.example.test"],
        "recipients": ["operations@smbflow.test"],
        "bodies": [
            "Hi team, I would like to schedule our Q3 QBR for next Tuesday at 2:00 PM EST. Please let me know if this time works.",
            "Let us connect for 20 minutes to align on the upcoming API release schedule."
        ]
    },
    {
        "scenario": "meeting_cancellation",
        "priority": "low",
        "labels": ["INBOX", "CALENDAR"],
        "subjects": ["Cancelled: Weekly Architecture Sync (Sept 10)", "Rescheduled: Product Review Call"],
        "senders": ["calendar-daemon@example.test", "alex.dev@smbflow.test"],
        "recipients": ["team@smbflow.test"],
        "bodies": [
            "The event 'Weekly Architecture Sync' scheduled for Sept 10 at 10:00 AM has been cancelled by the organizer.",
            "Hi all, I need to push our product review call to Thursday 3:00 PM due to a conflict."
        ]
    },
    {
        "scenario": "internal_operations_update",
        "priority": "normal",
        "labels": ["INBOX", "OPS"],
        "subjects": ["Maintenance Window Scheduled for Sept 15", "System Upgrade Notice: Database Cluster v3.2"],
        "senders": ["sysadmin@smbflow.test", "devops@smbflow.test"],
        "recipients": ["all-staff@smbflow.test"],
        "bodies": [
            "Please note: Routine database maintenance is scheduled for Sunday Sept 15 from 02:00 UTC to 04:00 UTC.",
            "We have successfully completed the migration of the secondary queue workers. All metrics nominal."
        ]
    },
    {
        "scenario": "vendor_communication",
        "priority": "normal",
        "labels": ["INBOX", "VENDOR"],
        "subjects": ["Vendor Security Questionnaire Update", "Service Terms Revision Notice — CloudStore"],
        "senders": ["security@cloudstore.example.test", "legal@vendornet.example.test"],
        "recipients": ["compliance@smbflow.test"],
        "bodies": [
            "Attached is our updated SOC2 Type II compliance audit report for the 2025-2026 period.",
            "Notice: CloudStore API rate limits will be updated effective October 1st. Please review revised developer terms."
        ]
    },
    {
        "scenario": "contract_document_notification",
        "priority": "high",
        "labels": ["INBOX", "LEGAL"],
        "subjects": ["Signature Required: Master Services Agreement v4.1", "Contract Executed: Partner Agreement #PA-882"],
        "senders": ["docusign-notify@contracts.example.test", "legal@partnercorp.example.test"],
        "recipients": ["legal@smbflow.test"],
        "bodies": [
            "Document 'MSA_SMBFlow_Final_v4.1.pdf' is ready for electronic signature. Please review and execute.",
            "The Partner Agreement #PA-882 has been fully executed by all parties. A copy is stored in the portal."
        ]
    },
    {
        "scenario": "product_issue",
        "priority": "high",
        "labels": ["INBOX", "BUG"],
        "subjects": ["Bug Report: CSV import failing on special characters", "Webhook delivery retries failing silently"],
        "senders": ["qa-automation@smbflow.test", "dev.lead@clientapp.example.test"],
        "recipients": ["engineering@smbflow.test"],
        "bodies": [
            "CSV bulk upload fails when input contains UTF-8 accented characters. Reproducible in v3.1 build.",
            "Webhook payloads with custom headers are failing exponential backoff retries. Need hotfix patch."
        ]
    },
    {
        "scenario": "feature_request",
        "priority": "low",
        "labels": ["INBOX", "FEEDBACK"],
        "subjects": ["Feature Request: Dark mode for Config Studio", "Feedback: Export runs to Parquet format"],
        "senders": ["feedback@community.example.test", "data.eng@clientco.example.test"],
        "recipients": ["product@smbflow.test"],
        "bodies": [
            "Our operators would love a dark theme option in the workflow DAG editor during late shifts.",
            "It would be very helpful if workflow execution history could be exported directly to S3 in Parquet format."
        ]
    },
    {
        "scenario": "delivery_status_update",
        "priority": "normal",
        "labels": ["INBOX", "LOGISTICS"],
        "subjects": ["Shipment Notification: Hardware Security Keys", "Tracking Update: Order #SH-40912"],
        "senders": ["logistics@hardwarevendor.example.test", "courier@express.example.test"],
        "recipients": ["ops@smbflow.test"],
        "bodies": [
            "Your order of 15 FIDO2 hardware security keys has shipped via FedEx (Tracking #7749201948).",
            "Order SH-40912 is out for delivery today. Signature will be required upon arrival."
        ]
    },
    {
        "scenario": "account_renewal_reminder",
        "priority": "high",
        "labels": ["INBOX", "RENEWAL"],
        "subjects": ["Annual Subscription Renewal Notice — 30 Days Remaining", "Expiration Warning: Domain Certificate"],
        "senders": ["renewals@smbflow.test", "cert-bot@security.example.test"],
        "recipients": ["admin@smbflow.test"],
        "bodies": [
            "Your annual plan for Organization 'Deconstruct' renews in 30 days (Oct 9, 2026). Contact your CSM to adjust seats.",
            "SSL Certificate for api.smbflow.test will expire in 14 days. Auto-renewal is active."
        ]
    },
    {
        "scenario": "follow_up_required",
        "priority": "high",
        "labels": ["INBOX", "FOLLOWUP"],
        "subjects": ["Follow-up: Unresolved Escalation #ESC-302", "Action Needed: Pending Security Audit Signoff"],
        "senders": ["compliance.officer@smbflow.test", "csm.manager@smbflow.test"],
        "recipients": ["lead.engineer@smbflow.test"],
        "bodies": [
            "Escalation #ESC-302 remains open after 48 hours without coordinator response. Immediate update required.",
            "The annual security controls audit signoff is pending your technical review. Please submit by Friday EOD."
        ]
    },
    {
        "scenario": "urgent_operational_issue",
        "priority": "urgent",
        "labels": ["INBOX", "URGENT", "OPS"],
        "subjects": ["URGENT: Storage volume 92% full on db-primary-01", "HIGH MEMORY: Worker process pool memory leak"],
        "senders": ["alerts@monitoring.example.test", "ops-bot@smbflow.test"],
        "recipients": ["oncall@smbflow.test"],
        "bodies": [
            "ALERT: Storage partition /var/lib/postgresql on db-primary-01 has exceeded 92% capacity threshold.",
            "Worker pool worker-instance-4 is consuming 94% memory. Automated restart pending in 5 minutes."
        ]
    },
    {
        "scenario": "general_informational_email",
        "priority": "low",
        "labels": ["INBOX", "INFO"],
        "subjects": ["Monthly Engineering Tech Talk Digest", "Industry Trends Briefing: Q3 2026 AI Automation"],
        "senders": ["newsletter@techdigest.example.test", "insights@analystgroup.example.test"],
        "recipients": ["team@smbflow.test"],
        "bodies": [
            "Here is the monthly roundup of engineering presentations including zero-downtime DB migrations and RAG indexing.",
            "Read our latest industry report on agentic AI workflows and human-in-the-loop governance trends."
        ]
    },
    {
        "scenario": "low_priority_newsletter",
        "priority": "low",
        "labels": ["INBOX", "NEWSLETTER"],
        "subjects": ["Developer Digest #142: Python 3.13 Features", "Cloud Architecture Weekly — Issue 409"],
        "senders": ["digest@devnews.example.test", "weekly@cloudweekly.example.test"],
        "recipients": ["devs@smbflow.test"],
        "bodies": [
            "In this edition: JIT compiler improvements in Python 3.13, async performance tuning, and new vector DB benchmarks.",
            "Top cloud news: multi-region failover strategies, serverless container scaling, and cost optimization tips."
        ]
    }
]

def generate_email_dataset() -> list[dict]:
    emails = []
    base_time = datetime(2026, 9, 8, 10, 0, 0)
    
    # We will generate 40 messages across the 20 scenarios (2 emails per scenario)
    msg_counter = 1
    thread_counter = 1
    
    for scenario_idx, sc in enumerate(SCENARIOS):
        for i in range(2):
            msg_id = f"seed-msg-{msg_counter:03d}"
            # Group into threads (some single, some multi-message conversations)
            if i == 1 and scenario_idx % 3 == 0:
                # Share thread_id with previous email to create thread conversation
                thread_id = f"seed-thread-{thread_counter - 1:03d}"
            else:
                thread_id = f"seed-thread-{thread_counter:03d}"
                thread_counter += 1

            sender = sc["senders"][i % len(sc["senders"])]
            recipient = sc["recipients"][i % len(sc["recipients"])]
            subject = sc["subjects"][i % len(sc["subjects"])]
            body = sc["bodies"][i % len(sc["bodies"])]
            
            # Timestamp spacing: spaced over recent days
            received_dt = base_time - timedelta(hours=(msg_counter * 3), minutes=(i * 17))
            
            email = {
                "id": f"seed-email-{msg_counter:03d}",
                "message_id": msg_id,
                "thread_id": thread_id,
                "from": sender,
                "to": recipient,
                "subject": subject,
                "body": body,
                "received_at": received_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "labels": sc["labels"],
                "scenario": sc["scenario"],
                "priority": sc["priority"],
                "data_origin": "synthetic",
                "is_test_data": True,
                "dataset": "email_workflow_demo"
            }
            emails.append(email)
            msg_counter += 1
            
    return emails

def main():
    SEED_DIR.mkdir(parents=True, exist_ok=True)
    out_path = SEED_DIR / "email_messages.json"
    
    emails = generate_email_dataset()
    out_path.write_text(json.dumps(emails, indent=2), encoding="utf-8")
    
    print(f"[OK] Generated {len(emails)} synthetic emails -> {out_path} ({round(out_path.stat().st_size/1024, 1)} KB)")

if __name__ == "__main__":
    main()

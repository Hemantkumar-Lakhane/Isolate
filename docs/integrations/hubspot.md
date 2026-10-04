# HubSpot CRM Integration Guide

## Overview
Sync customer leads, enrich contact records, and advance sales deals through CRM pipelines.

---

## Capabilities
- `hubspot.read_contacts`: Query CRM contacts and lead status.
- `hubspot.create_contact`: Insert new qualified leads discovered during email triage.
- `hubspot.update_deal`: Advance deals across pipeline stages.

---

## Configuration
1. Obtain a Private App Access Token from HubSpot Portal (**Settings > Integrations > Private Apps**).
2. Configure scopes: `crm.objects.contacts.read`, `crm.objects.contacts.write`, `crm.objects.deals.read`, `crm.objects.deals.write`.
3. In SMBFlow Integrations Marketplace, click **Configure Credentials** on HubSpot CRM and enter your Private App token.

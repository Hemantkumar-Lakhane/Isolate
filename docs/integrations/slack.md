# Slack Integration Guide

## Overview
Connects SMBFlow to Slack workspaces to broadcast operational alerts, coordinator summaries, and HITL approval request cards with deep links.

---

## Capabilities
- `slack.message.send`: Post operational alerts to designated channels.
- `slack.alert.post`: Post high-priority escalation cards with approval actions.
- `slack.channel.read`: Monitor thread conversations and resolution status.

---

## Configuration
1. Create a Slack App in your workspace (`api.slack.com/apps`).
2. Add Bot Token Scopes: `chat:write`, `channels:read`, `incoming-webhook`.
3. In SMBFlow Integrations Marketplace, click **Configure Credentials** on the Slack card.
4. Provide the `Bot Token` (`xoxb-...`) and optional alert channel IDs.

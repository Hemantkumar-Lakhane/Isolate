# Google OAuth 2.0 Integration Setup Guide

This guide walks you through configuring Google OAuth 2.0 for SMBFlow Tool Connections (Gmail, Google Calendar, Google Drive).

---

## 1. Prerequisites & Portal Navigation

1. Open the [Google Cloud Console](https://console.cloud.google.com/).
2. Select or create a new Project (e.g., `SMBFlow-Production`).
3. Navigate to **APIs & Services** → **Library**.

---

## 2. Enable Required Google APIs

Enable the following APIs:
- **Gmail API**
- **Google Calendar API**
- **Google Drive API**

---

## 3. Configure OAuth Consent Screen

1. Go to **APIs & Services** → **OAuth consent screen**.
2. Select **User Type**:
   - Choose **External** (or **Internal** if using a Google Workspace organization).
3. Fill in App Information:
   - **App Name**: `SMBFlow Tool Connector`
   - **User support email**: Your support or admin email.
   - **Developer contact information**: Your technical contact email.
4. **Scopes**:
   - Add least-privilege scopes:
     - `.../auth/userinfo.email`
     - `.../auth/userinfo.profile`
     - `openid`
     - `https://www.googleapis.com/auth/gmail.readonly`
     - `https://www.googleapis.com/auth/gmail.send`
     - `https://www.googleapis.com/auth/calendar.events`
     - `https://www.googleapis.com/auth/drive.readonly`
5. **Test Users**:
   - If your publishing status is **Testing**, add your personal/work Gmail address under **Test users**.

---

## 4. Create OAuth 2.0 Client Credentials

1. Navigate to **APIs & Services** → **Credentials**.
2. Click **+ Create Credentials** → **OAuth client ID**.
3. Application Type: **Web application**.
4. Name: `SMBFlow Backend Tool Connector`.
5. **Authorized redirect URIs**:
   Add the canonical FastAPI backend callback URL:
   ```text
   http://127.0.0.1:8000/api/v1/connections/oauth/gmail/callback
   http://127.0.0.1:8000/api/v1/connections/oauth/google_workspace/callback
   ```
6. Click **Create**.
7. Copy the **Client ID** and **Client Secret**.

---

## 5. Configure SMBFlow `.env`

Add the credentials to your local `.env` file:
```env
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-your-client-secret
```

---

## 6. Verification

1. Start SMBFlow: `.\start.ps1`.
2. Navigate to `http://localhost:5173/integrations`.
3. Locate **Gmail / Email** or **Google Workspace** and click **Connect with OAuth**.
4. Complete the Google consent screen.
5. You will be redirected back to `/integrations` with an active connection and green status badge.
6. Click **Test Live Connection** to verify latency and token health.

# LinkedIn OAuth 2.0 Integration Setup Guide

This guide walks you through configuring LinkedIn OAuth 2.0 for SMBFlow Tool Connections (Posting updates, marketing announcements, and profile identity).

---

## 1. Prerequisites & Portal Navigation

1. Open the [LinkedIn Developer Portal](https://developer.linkedin.com/).
2. Log in with your LinkedIn account and click **My Apps** → **Create App**.

---

## 2. App Creation

1. **App name**: `SMBFlow Tool Connector`
2. **LinkedIn Page**: Link your company or personal organization page.
3. **App logo**: Upload your company logo square image.
4. Check the legal agreement checkbox and click **Create app**.

---

## 3. Enable Required Products

In your app dashboard, go to the **Products** tab and request access to:
- **Share on LinkedIn** (Provides `w_member_social` for posting updates to member profiles).
- **Sign In with LinkedIn using OpenID Connect** (Provides `openid`, `profile`, `email` for member identity resolution).
- *(Optional / Advanced)* **Community Management API** (If posting to Company Organization Pages using `w_organization_social`).

---

## 4. Register Canonical Redirect URI

1. Navigate to the **Auth** tab.
2. Under **OAuth 2.0 settings**, locate **Authorized redirect URLs for your app**.
3. Click **+ Add redirect URL** and enter:
   ```text
   http://127.0.0.1:8000/api/v1/connections/oauth/linkedin/callback
   ```
4. Click **Update**.

---

## 5. Retrieve Client Credentials & Configure `.env`

1. Under the **Auth** tab, find:
   - **Client ID**
   - **Client Secret**
2. Add them to your local `.env` file:
   ```env
   LINKEDIN_CLIENT_ID=your-linkedin-client-id
   LINKEDIN_CLIENT_SECRET=your-linkedin-client-secret
   ```

---

## 6. Verification

1. Open SMBFlow: `http://localhost:5173/integrations`.
2. Locate **LinkedIn** in the marketplace grid.
3. Click **Connect with OAuth**.
4. Authorize the application on LinkedIn.
5. You will be redirected back to SMBFlow with status `Connected` and your LinkedIn member name displayed.
6. Click **Test Live Connection** to verify response latency.

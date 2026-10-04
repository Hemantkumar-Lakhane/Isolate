import asyncio
import json
import httpx
import websockets
import sys

TENANT_ID = "086133c3-7cd5-4cd4-bab4-30ec0f190d75"
API_URL = "http://localhost:8000/api/v1"
WS_URL = "ws://localhost:8000/ws/12345"

async def main():
    async with httpx.AsyncClient() as client:
        # Login
        print("Logging in...")
        resp = await client.post(f"{API_URL}/auth/login", json={"email": "admin@smbflow.com", "password": "admin123"})
        if resp.status_code != 200:
            print("Login failed:", resp.text)
            return
        token = resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Connect to WS
        print("Connecting to WebSocket...")
        try:
            ws = await websockets.connect(f"{WS_URL}?token={token}")
        except Exception as e:
            print(f"WS connection failed: {e}")
            return
            
        # Trigger
        print("Triggering workflow...")
        payload = {
            "workflow_name": "saas_churn_prevention",
            "tenant_id": TENANT_ID,
            "signal": {"customer_id": "C-123", "churn_risk": "high"}
        }
        resp = await client.post(f"{API_URL}/workflows/trigger", json=payload, headers=headers)
        if resp.status_code not in (200, 202):
            print("Trigger failed:", resp.text)
            return
            
        print("Trigger success:", resp.json())
        
        # Listen for WS events
        print("Listening for WS events (timeout 45s)...")
        while True:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=45.0)
                data = json.loads(msg)
                print(f"[WS] {data.get('type')}: {data.get('payload', {}).get('status', '')} | {data.get('payload', {}).get('agent', '')}")
                if data.get('type') == 'workflow_completed' or data.get('type') == 'workflow_failed':
                    print("Workflow ended.")
                    break
            except asyncio.TimeoutError:
                print("WS listen timeout.")
                break
        
        await ws.close()

if __name__ == "__main__":
    asyncio.run(main())

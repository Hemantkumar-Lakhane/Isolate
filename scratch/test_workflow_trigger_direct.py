import asyncio
from dotenv import load_dotenv
load_dotenv()
import httpx
from api.auth import create_access_token
from core.database import AsyncSessionLocal
from sqlalchemy import text

async def main():
    async with AsyncSessionLocal() as db:
        res = await db.execute(text('SELECT user_id, email, organization_id, role FROM organization_users LIMIT 1'))
        row = res.fetchone()
        print('DB User row:', row)
        user_id, email, org_id, role = str(row[0]), str(row[1]), str(row[2]), str(row[3])

    # Token WITHOUT org_id / tenant_id
    token = create_access_token({
        'sub': user_id,
        'email': email,
        'role': 'org_user'
    })
    print('Created token without org_id claim')

    async with httpx.AsyncClient(base_url='http://127.0.0.1:8000', timeout=10.0) as client:
        r = await client.get('/api/v1/auth/me', headers={'Authorization': f'Bearer {token}'})
        print('GET /api/v1/auth/me status:', r.status_code, r.json())

        r2 = await client.get('/api/v1/workflows/email_summarizer/trigger-info', headers={'Authorization': f'Bearer {token}'})
        print('GET trigger-info status:', r2.status_code, r2.json())

        payload = {
            'workflow_name': 'email_summarizer',
            'trigger_signal': {
                'source': 'manual_ui',
                'limit': 5
            }
        }
        r3 = await client.post('/api/v1/workflows/trigger', json=payload, headers={'Authorization': f'Bearer {token}'})
        print('POST /api/v1/workflows/trigger status:', r3.status_code, r3.json())
        assert r3.status_code == 200, f'Trigger failed: {r3.text}'
        run_data = r3.json()
        assert 'run_id' in run_data, 'run_id missing in response'
        print('SUCCESS! Workflow run created with run_id:', run_data['run_id'])

if __name__ == '__main__':
    asyncio.run(main())

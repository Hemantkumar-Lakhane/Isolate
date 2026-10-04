import json
import requests
import sys

def main():
    # 1. Read the config
    with open('config/clients/saas_demo.json', 'r') as f:
        demo_config = json.load(f)

    # Extract fields
    name = demo_config.get('client_name', 'TechFlow SaaS Inc.')
    industry = demo_config.get('industry', 'saas')
    
    # Remove top level fields that don't belong in config JSONB
    keys_to_remove = ['_meta', 'client_id', 'client_name', 'industry']
    config_payload = {k: v for k, v in demo_config.items() if k not in keys_to_remove}

    payload = {
        "name": name,
        "industry": industry,
        "config": config_payload
    }

    # 2. Login to get token
    login_url = "http://localhost:8000/api/v1/auth/login"
    login_data = {
        "email": "admin@smbflow.com",
        "password": "admin123"
    }
    
    print("Logging in...")
    login_resp = requests.post(login_url, json=login_data)
    if login_resp.status_code != 200:
        print(f"Login failed: {login_resp.text}")
        sys.exit(1)
        
    token = login_resp.json().get('access_token')
    headers = {"Authorization": f"Bearer {token}"}

    # 3. Create Tenant
    print(f"Creating tenant '{name}'...")
    tenant_url = "http://localhost:8000/api/v1/tenants"
    tenant_resp = requests.post(tenant_url, json=payload, headers=headers)
    
    if tenant_resp.status_code != 200:
        print(f"Tenant creation failed: {tenant_resp.text}")
        sys.exit(1)
        
    created_data = tenant_resp.json()
    print(f"Tenant created successfully! ID: {created_data.get('tenant_id')}")
    
    # 4. Verify with GET
    print("Verifying via GET /tenants...")
    get_resp = requests.get(tenant_url, headers=headers)
    if get_resp.status_code == 200:
        print("Tenants list:")
        for t in get_resp.json():
            print(f"- {t['name']} (ID: {t['id']})")
    else:
        print(f"GET /tenants failed: {get_resp.text}")

if __name__ == "__main__":
    main()

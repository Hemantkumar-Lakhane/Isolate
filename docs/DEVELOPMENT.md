# SMBFlow — Development Guide

## 1. Prerequisites
- Python 3.10+
- Node.js 18+
- Docker & Docker Compose (for local Redis and test runner)
- Supabase Project (Cloud or Local CLI)

## 2. Environment Variables (.env)
```env
SUPABASE_URL=https://your-supabase-project.supabase.co
SUPABASE_ANON_KEY=your-supabase-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-supabase-service-role-key
SUPABASE_JWT_SECRET=your-supabase-jwt-secret

REDIS_URL=redis://localhost:6379
VAULT_ENCRYPTION_KEY=your-fernet-encryption-key
OPENAI_API_KEY=your-openai-key
```

## 3. Quick Start
```powershell
# Install backend dependencies
pip install -r requirements.txt

# Start Redis via Docker
docker-compose up -d redis

# Run backend API
python -m uvicorn api.main:app --reload --port 8000

# Run frontend
cd frontend
npm install
npm run dev -- --port 5173
```

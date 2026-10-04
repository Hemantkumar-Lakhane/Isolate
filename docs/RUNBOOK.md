# SMBFlow Local Runbook

This document outlines the step-by-step process for starting the full SMBFlow application stack locally for development and testing.

## Prerequisites
- Docker & Docker Compose
- Python 3.10+
- Node.js 18+ & npm

## Quick Automated Setup & Launch (Recommended)

### 1. One-Time Setup
Drag and drop `setup.ps1` into your PowerShell terminal (or run `.\setup.ps1`):
```powershell
.\setup.ps1
# If execution policy prevents script execution:
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

### 2. Daily Application Launch
Drag and drop `start.ps1` into your PowerShell terminal (or run `.\start.ps1`):
```powershell
.\start.ps1
```

---

## Manual Step-by-Step Setup

## 1. Start the Database Infrastructure
The backend relies on PostgreSQL (exposed on host port **5434**) for relational data and vector storage, and Redis (port **6379**) for caching.

From the root of the repository, start the Docker containers:
```powershell
docker-compose up -d postgres redis
```

## 2. Start the FastAPI Backend
Open a terminal at the root of the repository (`C:\Users\lakha\ml_cp\SMBFlow`) and run:
```powershell
.\venv\Scripts\python.exe main.py api
```

## 3. Start the React Frontend
Open a second terminal window, navigate to `frontend`, and run:
```powershell
cd frontend
npm run dev
```
*This starts the frontend development server on `http://localhost:5173`.*

## 4. Access the Application
1. Open your web browser and navigate to the authentication page:
   [http://localhost:5173/auth](http://localhost:5173/auth)
2. Log in based on your desired role:
   - **SMB Owner (Business User)**:
     - **Email:** `demo@tenant.com` *(Replace with seeded tenant email)*
     - **Password:** `demo123`
     - **Redirect:** `/dashboard` (The SMB Owner Dashboard)
   - **SMBFlow Admin (Super Admin / OpsGrid Team)**:
     - **Email:** `admin@smbflow.com` (seeded in `db/init.sql`)
     - **Password:** `admin123`
     - **Redirect:** `/admin` (The Platform God View - *To be implemented*)

---

## 5. API Testing & Documentation
While the backend is running, you can interact with the API endpoints directly:

- **Interactive API Documentation (Swagger UI)**:
  [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Alternative API Documentation (ReDoc)**:
  [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
- **OpenAPI JSON Schema**:
  [http://127.0.0.1:8000/openapi.json](http://127.0.0.1:8000/openapi.json)
- **Health Check Endpoint**:
  [http://127.0.0.1:8000/api/v1/health](http://127.0.0.1:8000/api/v1/health)

---

## Troubleshooting
- **Backend crash on startup:** Ensure `docker-compose up -d` has fully initialized the database before starting the backend.
- **Port conflicts:** Make sure ports `8000` (FastAPI), `5173` (Vite), `5432` (Postgres), and `6379` (Redis) are not occupied by other applications.
- **Data not loading:** Verify your `.env` file is properly configured to point to the local Docker containers.

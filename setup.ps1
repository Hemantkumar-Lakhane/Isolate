param()

Set-Location $PSScriptRoot

Write-Host "Starting local setup for SMBFlow..." -ForegroundColor Cyan

# 1. Check Prerequisites
$requiredTools = @("python", "node", "npm", "docker", "docker-compose")
foreach ($tool in $requiredTools) {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
        Write-Error "Required tool '$tool' is not installed or not in PATH."
        exit 1
    }
}
Write-Host "All prerequisites found." -ForegroundColor Green

# 2. Virtual Environment
if (-not (Test-Path "venv")) {
    Write-Host "Creating Python virtual environment..."
    python -m venv venv
}

# 3. .env check
if (-not (Test-Path ".env")) {
    Write-Host "Copying .env.example to .env..."
    Copy-Item ".env.example" ".env"
}

# 4. Install requirements first so we can validate Vault key using cryptography
Write-Host "Installing backend dependencies (this may take a minute)..."
$env:PYTHONUTF8=1
.\venv\Scripts\python.exe -m pip install -r requirements.txt

# 5. VAULT_ENCRYPTION_KEY validation & generation
Write-Host "Validating VAULT_ENCRYPTION_KEY..."
$pythonScript = @"
import os
import sys
from dotenv import load_dotenv, set_key
from cryptography.fernet import Fernet

env_path = '.env'
load_dotenv(env_path)
key = os.getenv('VAULT_ENCRYPTION_KEY')

if not key or key == 'generate using python' or key.strip() == '':
    new_key = Fernet.generate_key().decode()
    set_key(env_path, 'VAULT_ENCRYPTION_KEY', new_key)
    print('generated')
else:
    try:
        Fernet(key.encode('utf-8'))
        print('valid')
    except Exception as e:
        print(f'invalid: {e}')
        sys.exit(1)
"@

$keyStatus = .\venv\Scripts\python.exe -c $pythonScript
if ($LASTEXITCODE -ne 0) {
    Write-Error "The existing VAULT_ENCRYPTION_KEY in .env is invalid. $keyStatus"
    Write-Error "Please fix it manually or remove the line so it can be generated."
    exit 1
}
if ($keyStatus -eq "generated") {
    Write-Host "Generated and safely saved a new VAULT_ENCRYPTION_KEY." -ForegroundColor Green
} else {
    Write-Host "Existing VAULT_ENCRYPTION_KEY is valid." -ForegroundColor Green
}

# 6. Start Infrastructure
Write-Host "Starting Docker infrastructure..."
docker-compose up -d postgres redis

Write-Host "Waiting for PostgreSQL to be healthy..."
$retryCount = 0
while ($retryCount -lt 15) {
    $status = docker inspect --format="{{if .State.Health}}{{.State.Health.Status}}{{end}}" opsgrid_postgres 2>$null
    if ($status -eq "healthy") { 
        Write-Host "PostgreSQL is healthy!" -ForegroundColor Green
        break 
    }
    Start-Sleep -Seconds 2
    $retryCount++
}

if ($status -ne "healthy") {
    Write-Error "PostgreSQL failed to become healthy. Please check docker logs opsgrid_postgres."
    exit 1
}

# 7. Database Seeding (Idempotent Local JSON Generation)
Write-Host "Generating local seed data JSON files (safe and idempotent)..."
.\venv\Scripts\python.exe db/seed/saas_seed.py
.\venv\Scripts\python.exe db/seed/email_seed.py

# 8. Frontend Dependencies
Write-Host "Installing frontend dependencies..."
Push-Location frontend
npm install
Pop-Location

Write-Host ""
Write-Host "Setup complete!" -ForegroundColor Green
Write-Host "Run .\start.ps1 to launch the application." -ForegroundColor Cyan

param()

Set-Location $PSScriptRoot

Write-Host "Starting SMBFlow Local Environment..." -ForegroundColor Cyan

# =============================================================================
# Process & Port Helper Functions for Safe Project Switching
# =============================================================================

function Get-PortProcess {
    param([int]$Port)
    $connections = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if (-not $connections) { return @() }
    
    $processes = @()
    foreach ($conn in $connections) {
        $pidNum = $conn.OwningProcess
        if ($pidNum -le 4) { continue }
        $proc = Get-Process -Id $pidNum -ErrorAction SilentlyContinue
        $cimProc = Get-CimInstance Win32_Process -Filter "ProcessId = $pidNum" -ErrorAction SilentlyContinue
        $cmdLine = if ($cimProc -and $cimProc.CommandLine) { $cimProc.CommandLine } else { "" }
        $execPath = if ($proc -and $proc.Path) { $proc.Path } else { "" }
        
        $processes += [PSCustomObject]@{
            Port        = $Port
            PID         = $pidNum
            ProcessName = if ($proc) { $proc.ProcessName } else { "Unknown" }
            Path        = $execPath
            CommandLine = $cmdLine
        }
    }
    return $processes
}

function Test-ProjectProcess {
    param(
        [Parameter(Mandatory=$true)]
        $ProcessInfo,
        [Parameter(Mandatory=$true)]
        [string]$ProjectName
    )
    if (-not $ProcessInfo) { return $false }
    $searchStr = "$($ProcessInfo.CommandLine) $($ProcessInfo.Path)"
    switch -Regex ($ProjectName) {
        "SMBFlow" {
            return ($searchStr -match "(?i)SMBFlow")
        }
        "welfare-intelligence-platform" {
            return ($searchStr -match "(?i)welfare-intelligence-platform")
        }
        default {
            $escaped = [Regex]::Escape($ProjectName)
            return ($searchStr -match "(?i)$escaped")
        }
    }
}

function Stop-ProjectProcessSafely {
    param(
        [Parameter(Mandatory=$true)]
        $ProcessInfo,
        [Parameter(Mandatory=$true)]
        [string]$Reason
    )
    Write-Host "Stopping process PID $($ProcessInfo.PID) ($($ProcessInfo.ProcessName)) on port $($ProcessInfo.Port) [$Reason]..." -ForegroundColor Yellow
    try {
        taskkill /PID $ProcessInfo.PID /F /T 2>$null
        Stop-Process -Id $ProcessInfo.PID -Force -ErrorAction SilentlyContinue
    } catch {
        Write-Host "Warning: Failed to stop process PID $($ProcessInfo.PID): $_" -ForegroundColor Yellow
    }
}

function Wait-ForPortRelease {
    param(
        [int]$Port,
        [int]$TimeoutSec = 5
    )
    $elapsed = 0
    while ($elapsed -lt $TimeoutSec) {
        $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        if (-not $conn) { return $true }
        # Verify if process actually exists
        $pidNum = $conn.OwningProcess
        if ($pidNum -gt 4 -and -not (Get-Process -Id $pidNum -ErrorAction SilentlyContinue)) {
            return $true # Orphanned TCP entry, socket available
        }
        Start-Sleep -Milliseconds 500
        $elapsed += 0.5
    }
    return (-not (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue))
}

function Ensure-PortReadyForProject {
    param(
        [int]$Port,
        [string]$CurrentProject = "SMBFlow",
        [string]$OtherProject   = "welfare-intelligence-platform",
        [string]$ServiceName    = "Service"
    )
    $portProcs = Get-PortProcess -Port $Port
    if (-not $portProcs -or $portProcs.Count -eq 0) {
        return $false
    }

    foreach ($p in $portProcs) {
        # Check if active process exists for PID
        if (-not (Get-Process -Id $p.PID -ErrorAction SilentlyContinue)) {
            continue
        }

        if (Test-ProjectProcess -ProcessInfo $p -ProjectName $CurrentProject) {
            Write-Host "$ServiceName is already running on port $Port for $CurrentProject (PID: $($p.PID))." -ForegroundColor Yellow
            return $true
        }
        elseif (Test-ProjectProcess -ProcessInfo $p -ProjectName $OtherProject) {
            Write-Host "Port $Port is occupied by $OtherProject (PID: $($p.PID)). Safely stopping it to switch projects..." -ForegroundColor Cyan
            Stop-ProjectProcessSafely -ProcessInfo $p -Reason "Switching to $CurrentProject"
            $released = Wait-ForPortRelease -Port $Port -TimeoutSec 5
            if ($released) {
                Write-Host "Port $Port released successfully." -ForegroundColor Green
            } else {
                Write-Host "Warning: Port $Port still showing active connection after 5s." -ForegroundColor Yellow
            }
        }
        else {
            Write-Host "==========================================" -ForegroundColor Red
            Write-Host "PORT CONFLICT ERROR on port $Port" -ForegroundColor Red
            Write-Host "Port $Port is occupied by an unrelated application:" -ForegroundColor Red
            Write-Host "  PID:          $($p.PID)" -ForegroundColor Red
            Write-Host "  Process Name: $($p.ProcessName)" -ForegroundColor Red
            Write-Host "  Executable:   $($p.Path)" -ForegroundColor Red
            Write-Host "  Command Line: $($p.CommandLine)" -ForegroundColor Red
            Write-Host "" -ForegroundColor Red
            Write-Host "$CurrentProject will NOT kill unrelated processes automatically." -ForegroundColor Red
            Write-Host "Please close the application on port $Port or choose a different port." -ForegroundColor Red
            Write-Host "==========================================" -ForegroundColor Red
            exit 1
        }
    }
    return $false
}

# =============================================================================
# 1. Start Infrastructure & Fixtures
# =============================================================================

Write-Host "Ensuring Redis container is running..." -ForegroundColor Gray
try {
    docker-compose up -d redis 2>$null
} catch {
    Write-Host "Notice: Docker not available or Redis already running natively." -ForegroundColor Yellow
}

$emailFixture = Join-Path $PSScriptRoot "db\seed\data\email_messages.json"
if (-not (Test-Path $emailFixture)) {
    Write-Host "Generating Email Summarizer fixture (email_messages.json)..." -ForegroundColor Cyan
    .\venv\Scripts\python.exe db/seed/email_seed.py
    if ($LASTEXITCODE -ne 0) {
        Write-Host "WARNING: Email fixture generation failed. The Email Summarizer workflow may have no data." -ForegroundColor Yellow
        Write-Host "         Retry manually with: .\venv\Scripts\python.exe db/seed/email_seed.py" -ForegroundColor Yellow
    }
} else {
    Write-Host "Email Summarizer fixture already present (email_messages.json) - skipping seed generation." -ForegroundColor Gray
}

# =============================================================================
# 2. Check and start Backend (Port 8000)
# =============================================================================

$backendRunning = Ensure-PortReadyForProject -Port 8000 -CurrentProject "SMBFlow" -OtherProject "welfare-intelligence-platform" -ServiceName "Backend API"
if (-not $backendRunning) {
    Write-Host "Starting Backend API in a new window..." -ForegroundColor Green
    Start-Process powershell.exe -ArgumentList "-NoExit", "-Command", "& '.\venv\Scripts\python.exe' main.py api" -WorkingDirectory $PWD -WindowStyle Normal
}

# =============================================================================
# 3. Check and start Frontend (Port 5173)
# =============================================================================

$frontendRunning = Ensure-PortReadyForProject -Port 5173 -CurrentProject "SMBFlow" -OtherProject "welfare-intelligence-platform" -ServiceName "Frontend"
if (-not $frontendRunning) {
    Write-Host "Starting Frontend in a new window..." -ForegroundColor Green
    Start-Process powershell.exe -ArgumentList "-NoExit", "-Command", "cd frontend; npm run dev" -WorkingDirectory $PWD -WindowStyle Normal
}

# =============================================================================
# 4. Wait for backend health
# =============================================================================

$healthUrl = "http://127.0.0.1:8000/api/v1/health"
$maxAttempts = 30   # 30 x 2s = up to 60s
$backendHealthy = $false

Write-Host ""
Write-Host "Waiting for backend to become healthy at $healthUrl ..." -ForegroundColor Gray
for ($i = 1; $i -le $maxAttempts; $i++) {
    try {
        $resp = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 3 -ErrorAction Stop
        if ($resp -and $resp.status -eq "ok") {
            $backendHealthy = $true
            break
        }
    } catch {
        # Backend not accepting connections yet — keep polling.
    }
    Start-Sleep -Seconds 2
    Write-Host "  ...still waiting for backend ($i/$maxAttempts)" -ForegroundColor DarkGray
}

Write-Host ""
if ($backendHealthy) {
    Write-Host "==========================================" -ForegroundColor Cyan
    Write-Host "SMBFlow is running!" -ForegroundColor Green
    Write-Host "Frontend Dashboard:   http://localhost:5173"
    Write-Host "API Base URL:         http://127.0.0.1:8000"
    Write-Host "API Testing (Docs):   http://127.0.0.1:8000/docs"
    Write-Host "API Health Check:     http://127.0.0.1:8000/api/v1/health"
    Write-Host "API ReDoc View:       http://127.0.0.1:8000/redoc"
    Write-Host "==========================================" -ForegroundColor Cyan
} else {
    Write-Host "==========================================" -ForegroundColor Red
    Write-Host "SMBFlow backend did NOT become healthy." -ForegroundColor Red
    Write-Host "The API at $healthUrl did not respond with status 'ok' after $($maxAttempts * 2)s." -ForegroundColor Red
    Write-Host ""
    Write-Host "ACTION: Check the separate 'python main.py api' backend window for the real" -ForegroundColor Yellow
    Write-Host "        error (stack trace, port 8000 conflict, or database connection failure)." -ForegroundColor Yellow
    Write-Host "        The frontend may still be starting on http://localhost:5173, but the app" -ForegroundColor Yellow
    Write-Host "        will not work until the backend is healthy." -ForegroundColor Yellow
    Write-Host "==========================================" -ForegroundColor Red
    exit 1
}

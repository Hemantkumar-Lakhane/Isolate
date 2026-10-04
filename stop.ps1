param()

Set-Location $PSScriptRoot

Write-Host "Stopping SMBFlow Local Environment..." -ForegroundColor Cyan

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
        "SMBFlow" { return ($searchStr -match "(?i)SMBFlow") }
        "welfare-intelligence-platform" { return ($searchStr -match "(?i)welfare-intelligence-platform") }
        default {
            $escaped = [Regex]::Escape($ProjectName)
            return ($searchStr -match "(?i)$escaped")
        }
    }
}

function Stop-ProjectPortSafely {
    param(
        [int]$Port,
        [string]$ProjectName = "SMBFlow"
    )
    $procs = Get-PortProcess -Port $Port
    if ($procs -and $procs.Count -gt 0) {
        foreach ($p in $procs) {
            if (Test-ProjectProcess -ProcessInfo $p -ProjectName $ProjectName) {
                Write-Host "Stopping $ProjectName process '$($p.ProcessName)' (PID: $($p.PID)) on port $Port..." -ForegroundColor Cyan
                Stop-Process -Id $p.PID -Force -ErrorAction SilentlyContinue
            } else {
                Write-Host "Skipping process PID $($p.PID) ($($p.ProcessName)) on port $Port - does not belong to $ProjectName." -ForegroundColor Yellow
            }
        }
    } else {
        Write-Host "No process found listening on port $Port." -ForegroundColor DarkGray
    }
}

# 1. Stop Backend on port 8000
Write-Host "Stopping Backend..."
Stop-ProjectPortSafely -Port 8000 -ProjectName "SMBFlow"

# 2. Stop Frontend on port 5173
Write-Host "Stopping Frontend..."
Stop-ProjectPortSafely -Port 5173 -ProjectName "SMBFlow"

# 3. Stop Docker Infrastructure
Write-Host "Stopping Docker infrastructure safely (docker-compose stop)..."
try {
    docker-compose stop 2>$null
} catch {}

Write-Host "SMBFlow has been stopped." -ForegroundColor Green

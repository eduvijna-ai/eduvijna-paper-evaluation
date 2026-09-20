#Requires -Version 5.1
<#
.SYNOPSIS
  Ensure Docker deps, free host port 18000, and apply committed migrations for F5.

.DESCRIPTION
  Starts only postgres, redis, and minio (idempotent). Does not start Docker api/worker.
  Stops compose api/worker if they hold publish port 18000 so host uvicorn can bind.
  Applies Alembic upgrade head only - never generates migrations, never reseeds, never resets volumes.
#>
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

function Write-Step([string]$Message) {
    Write-Host "==> $Message"
}

function Fail([string]$Message) {
    Write-Host "ERROR: $Message" -ForegroundColor Red
    exit 1
}

function Import-DotEnv([string]$Path) {
    Get-Content -LiteralPath $Path | ForEach-Object {
        $line = $_.Trim()
        if ($line -eq "" -or $line.StartsWith("#")) {
            return
        }
        $idx = $line.IndexOf("=")
        if ($idx -lt 1) {
            return
        }
        $key = $line.Substring(0, $idx).Trim()
        $value = $line.Substring($idx + 1).Trim()
        if (
            ($value.StartsWith('"') -and $value.EndsWith('"')) -or
            ($value.StartsWith("'") -and $value.EndsWith("'"))
        ) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        Set-Item -Path "Env:$key" -Value $value
    }
}

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
Set-Location $RepoRoot

Write-Step "Checking Docker"
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Fail "Docker is not on PATH. Install Docker Desktop and retry."
}
docker info --format "{{.ServerVersion}}" | Out-Null
if ($LASTEXITCODE -ne 0) {
    Fail "Docker is installed but the engine is not running. Start Docker Desktop and retry."
}

$EnvExample = Join-Path $RepoRoot "apps/api/.env.local.example"
$EnvLocal = Join-Path $RepoRoot "apps/api/.env.local"
if (-not (Test-Path -LiteralPath $EnvExample)) {
    Fail "Missing $EnvExample"
}
if (-not (Test-Path -LiteralPath $EnvLocal)) {
    Copy-Item -LiteralPath $EnvExample -Destination $EnvLocal
    Write-Step "Created apps/api/.env.local from .env.local.example"
}

$WebEnvExample = Join-Path $RepoRoot "apps/web/.env.local.example"
$WebEnvLocal = Join-Path $RepoRoot "apps/web/.env.local"
if ((Test-Path -LiteralPath $WebEnvExample) -and -not (Test-Path -LiteralPath $WebEnvLocal)) {
    Copy-Item -LiteralPath $WebEnvExample -Destination $WebEnvLocal
    Write-Step "Created apps/web/.env.local from .env.local.example"
}

$VenvUnix = Join-Path $RepoRoot "apps/api/.venv/bin/python"
$VenvWin = Join-Path $RepoRoot "apps/api/.venv/Scripts/python.exe"
if (Test-Path -LiteralPath $VenvWin) {
    $Python = $VenvWin
} elseif (Test-Path -LiteralPath $VenvUnix) {
    $Python = $VenvUnix
} else {
    Fail "Missing apps/api/.venv. From apps/api run: python -m venv .venv ; .venv\Scripts\python.exe -m pip install -e `".[dev]`""
}

function Get-ComposeServiceHealth([string]$Service) {
    $cid = (docker compose ps -q $Service | Select-Object -First 1)
    if (-not $cid) {
        return "missing"
    }
    $health = docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' $cid
    if ($LASTEXITCODE -ne 0 -or -not $health) {
        return "unknown"
    }
    return $health.Trim()
}

Write-Step "Starting Docker dependencies (postgres redis minio) - not api/worker"
docker compose up -d --wait postgres redis minio
if ($LASTEXITCODE -ne 0) {
    Write-Step "docker compose --wait failed; retrying without --wait and polling health"
    docker compose up -d postgres redis minio
    if ($LASTEXITCODE -ne 0) {
        Fail "Could not start postgres, redis, and minio via docker compose."
    }
    $deadline = (Get-Date).AddSeconds(90)
    foreach ($service in @("postgres", "redis", "minio")) {
        $healthy = $false
        while ((Get-Date) -lt $deadline) {
            $status = Get-ComposeServiceHealth $service
            if ($status -eq "healthy" -or $status -eq "running") {
                $healthy = $true
                break
            }
            Start-Sleep -Seconds 2
        }
        if (-not $healthy) {
            Fail "Dependency '$service' did not become healthy in time."
        }
    }
}

# Host F5 binds 127.0.0.1:18000 - stop compose api/worker if present (volumes preserved).
$running = @(docker compose ps --status running --services 2>$null)
if ($LASTEXITCODE -eq 0) {
    $toStop = @($running | Where-Object { $_ -eq "api" -or $_ -eq "worker" })
    if ($toStop.Count -gt 0) {
        Write-Step ("Stopping Docker api/worker to free port 18000 (volumes kept): " + ($toStop -join ", "))
        docker compose stop @toStop
        if ($LASTEXITCODE -ne 0) {
            Fail "Could not stop Docker api/worker. Free port 18000 manually and retry."
        }
    }
}

Write-Step "Loading apps/api/.env.local into this process"
Import-DotEnv $EnvLocal
if (-not $env:DATABASE_URL) {
    Fail "DATABASE_URL is not set after loading apps/api/.env.local"
}
if ($env:DATABASE_URL -match "@(postgres|redis|minio)(:|/|$)") {
    Fail "apps/api/.env.local still uses Docker DNS names. Host F5 must use 127.0.0.1 publish ports."
}

Write-Step "Alembic upgrade head (committed migrations only; no seed/reset)"
Push-Location (Join-Path $RepoRoot "apps/api")
try {
    & $Python -m alembic -c alembic.ini upgrade head
    if ($LASTEXITCODE -ne 0) {
        Fail "Alembic upgrade head failed. Confirm PostgreSQL is reachable at 127.0.0.1:15432."
    }
    & $Python -m alembic -c alembic.ini current
    if ($LASTEXITCODE -ne 0) {
        Fail "Could not read Alembic current revision after upgrade."
    }
} finally {
    Pop-Location
}

Write-Step "Local API dependencies ready. F5 API listens on http://127.0.0.1:18000 (Docker volumes preserved)."
exit 0

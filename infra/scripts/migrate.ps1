$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path (Join-Path $PSScriptRoot "../.."))

$runningServices = docker compose ps --status running --services
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if ($runningServices -contains "api") {
    docker compose exec -T api alembic -c /app/alembic.ini upgrade head
} else {
    $Python = if (Test-Path "apps/api/.venv/Scripts/python.exe") {
        Resolve-Path "apps/api/.venv/Scripts/python.exe"
    } else {
        "python"
    }
    Push-Location "apps/api"
    try {
        & $Python -m alembic -c alembic.ini upgrade head
    } finally {
        Pop-Location
    }
}
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

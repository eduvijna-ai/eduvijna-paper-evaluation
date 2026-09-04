$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path (Join-Path $PSScriptRoot "../.."))

docker compose down -v
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
docker compose up -d --build
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& (Join-Path $PSScriptRoot "migrate.ps1")

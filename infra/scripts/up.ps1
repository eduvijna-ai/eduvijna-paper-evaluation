$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path (Join-Path $PSScriptRoot "../.."))
docker compose up -d --build
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

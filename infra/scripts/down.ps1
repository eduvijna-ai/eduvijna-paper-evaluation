$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path (Join-Path $PSScriptRoot "../.."))
docker compose down
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

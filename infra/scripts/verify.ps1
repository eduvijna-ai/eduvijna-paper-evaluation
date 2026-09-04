$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
Set-Location $RepoRoot

docker compose config --quiet
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& (Join-Path $PSScriptRoot "lint.ps1")
& (Join-Path $PSScriptRoot "typecheck.ps1")
& (Join-Path $PSScriptRoot "test.ps1")
Set-Location $RepoRoot
node packages/contracts/scripts/validate.mjs
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

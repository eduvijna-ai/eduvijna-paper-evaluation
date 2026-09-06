$ErrorActionPreference = "Stop"
Set-Location (Resolve-Path (Join-Path $PSScriptRoot "../../apps/api"))
$Python = if (Test-Path ".venv/Scripts/python.exe") {
    Resolve-Path ".venv/Scripts/python.exe"
} else {
    "python"
}
& $Python -m ruff check .
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# SAFE STUB: orchestrate synthetic DR restore drill on disposable resources only.
# Does NOT destroy MAT volumes. Does NOT run docker compose down -v.
$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $PSCommandPath
$ScriptName = Split-Path -Leaf $PSCommandPath

function Refuse([string]$Message) {
  [Console]::Error.WriteLine("${ScriptName}: REFUSED: $Message")
  exit 2
}

function Require-Var([string]$Name) {
  $val = [Environment]::GetEnvironmentVariable($Name)
  if ([string]::IsNullOrWhiteSpace($val)) { Refuse "missing required env var $Name" }
  return $val
}

$backupDir = Require-Var "DISPOSABLE_BACKUP_DIR"
$confirm = Require-Var "DISPOSABLE_RESTORE_CONFIRM"
if ($confirm -ne "YES_DISPOSABLE_ONLY") {
  Refuse "set DISPOSABLE_RESTORE_CONFIRM=YES_DISPOSABLE_ONLY"
}

$dbUrl = [Environment]::GetEnvironmentVariable("DISPOSABLE_DATABASE_URL")
if ([string]::IsNullOrWhiteSpace($dbUrl)) {
  $null = Require-Var "DISPOSABLE_POSTGRES_HOST"
  $null = Require-Var "DISPOSABLE_POSTGRES_PORT"
  $null = Require-Var "DISPOSABLE_POSTGRES_DB"
  $null = Require-Var "DISPOSABLE_POSTGRES_USER"
}

$null = Require-Var "DISPOSABLE_S3_ENDPOINT_URL"
$null = Require-Var "DISPOSABLE_S3_BUCKET"

$env:DISPOSABLE_BACKUP_PATH = Join-Path $backupDir "postgres.dump"
Write-Host "${ScriptName}: step 1/4 backup-postgres (stub)"
& "$ScriptDir/backup-postgres.ps1"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$env:DISPOSABLE_BACKUP_PATH = Join-Path $backupDir "object-storage"
Write-Host "${ScriptName}: step 2/4 backup-object-storage (stub)"
& "$ScriptDir/backup-object-storage.ps1"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$env:DISPOSABLE_BACKUP_PATH = Join-Path $backupDir "postgres.dump"
Write-Host "${ScriptName}: step 3/4 restore-postgres (stub) — recreate disposable DB out-of-band"
& "$ScriptDir/restore-postgres.ps1"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$env:DISPOSABLE_BACKUP_PATH = Join-Path $backupDir "object-storage"
Write-Host "${ScriptName}: step 4/4 restore-object-storage (stub)"
& "$ScriptDir/restore-object-storage.ps1"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "${ScriptName}: STUB drill complete. Record observations in docs/production/BACKUP_RESTORE_DR.md"
Write-Host "${ScriptName}: Redis is not SoT — expect empty broker after synthetic rebuild."
exit 0

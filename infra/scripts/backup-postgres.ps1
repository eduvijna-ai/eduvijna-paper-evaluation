# SAFE STUB: backup disposable PostgreSQL only.
# Requires DISPOSABLE_* env vars. Refuses MAT Compose defaults unless OVERRIDE_MAT_SAFETY=1.
# NEVER point at founder MAT volumes. Does not run docker compose down -v.
$ErrorActionPreference = "Stop"
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

function Test-MatDbName([string]$Name) {
  return $Name -in @("eduvijna", "eduvijna_mat", "postgres")
}

function Test-MatPort([string]$Port) {
  return $Port -in @("15432")
}

function Test-LooksDisposable([string]$Value) {
  return $Value -match "(?i)disposable|drill|tmp|throwaway"
}

$backupPath = Require-Var "DISPOSABLE_BACKUP_PATH"
$dbUrl = [Environment]::GetEnvironmentVariable("DISPOSABLE_DATABASE_URL")
$dbName = [Environment]::GetEnvironmentVariable("DISPOSABLE_POSTGRES_DB")
$dbPort = [Environment]::GetEnvironmentVariable("DISPOSABLE_POSTGRES_PORT")

if (-not [string]::IsNullOrWhiteSpace($dbUrl)) {
  $targetDesc = $dbUrl
  if ([string]::IsNullOrWhiteSpace($dbName) -and $dbUrl -match "/([^/?]+)(\?|$)") { $dbName = $Matches[1] }
  if ([string]::IsNullOrWhiteSpace($dbPort) -and $dbUrl -match ":(\d+)/") { $dbPort = $Matches[1] }
} else {
  $hostName = Require-Var "DISPOSABLE_POSTGRES_HOST"
  $dbPort = Require-Var "DISPOSABLE_POSTGRES_PORT"
  $dbName = Require-Var "DISPOSABLE_POSTGRES_DB"
  $null = Require-Var "DISPOSABLE_POSTGRES_USER"
  $targetDesc = "${hostName}:${dbPort}/${dbName}"
}

$override = [Environment]::GetEnvironmentVariable("OVERRIDE_MAT_SAFETY")
if ((Test-MatDbName $dbName) -or (Test-MatPort $dbPort)) {
  if ($override -ne "1") {
    Refuse "target looks like MAT/local Compose default (db='$dbName' port='$dbPort'). Use disposable names/ports or set OVERRIDE_MAT_SAFETY=1 (still prefer disposable)."
  }
  Write-Warning "${ScriptName}: OVERRIDE_MAT_SAFETY=1 set; still prefer disposable targets."
}

if (-not (Test-LooksDisposable $dbName) -and -not (Test-LooksDisposable $backupPath) -and -not (Test-LooksDisposable $targetDesc)) {
  if ($override -ne "1") {
    Refuse "name/path does not look disposable (include disposable|drill|tmp). Refusing."
  }
}

Write-Host ("{0}: STUB - would backup Postgres from [{1}] to [{2}]" -f $ScriptName, $targetDesc, $backupPath)
Write-Host ("{0}: Implement with pg_dump against DISPOSABLE_* only. No MAT volumes." -f $ScriptName)
exit 0

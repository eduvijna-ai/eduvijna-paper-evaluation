# SAFE STUB: restore PostgreSQL into disposable instance only.
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
$confirm = Require-Var "DISPOSABLE_RESTORE_CONFIRM"
if ($confirm -ne "YES_DISPOSABLE_ONLY") {
  Refuse "set DISPOSABLE_RESTORE_CONFIRM=YES_DISPOSABLE_ONLY to acknowledge isolated restore"
}

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
    Refuse "restore target looks like MAT/local Compose default (db='$dbName' port='$dbPort')."
  }
  Write-Warning "${ScriptName}: OVERRIDE_MAT_SAFETY=1 set; still prefer disposable targets."
}

if (-not (Test-LooksDisposable $dbName) -and -not (Test-LooksDisposable $targetDesc)) {
  if ($override -ne "1") {
    Refuse "restore target name does not look disposable (include disposable|drill|tmp)."
  }
}

Write-Host ("{0}: STUB - would restore [{1}] into [{2}]" -f $ScriptName, $backupPath, $targetDesc)
Write-Host ("{0}: NEVER destroy founder MAT volumes." -f $ScriptName)
exit 0

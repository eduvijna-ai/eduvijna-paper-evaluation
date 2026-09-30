# SAFE STUB: restore object storage into disposable bucket only.
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

function Test-MatBucket([string]$Name) {
  return $Name -in @("eduvijna-papers", "eduvijna")
}

function Test-MatEndpoint([string]$Url) {
  return $Url -match ":19000(/|$)"
}

function Test-LooksDisposable([string]$Value) {
  return $Value -match "(?i)disposable|drill|tmp|throwaway"
}

$endpoint = Require-Var "DISPOSABLE_S3_ENDPOINT_URL"
$bucket = Require-Var "DISPOSABLE_S3_BUCKET"
$backupPath = Require-Var "DISPOSABLE_BACKUP_PATH"
$confirm = Require-Var "DISPOSABLE_RESTORE_CONFIRM"
if ($confirm -ne "YES_DISPOSABLE_ONLY") {
  Refuse "set DISPOSABLE_RESTORE_CONFIRM=YES_DISPOSABLE_ONLY to acknowledge isolated restore"
}

$override = [Environment]::GetEnvironmentVariable("OVERRIDE_MAT_SAFETY")
if ((Test-MatBucket $bucket) -or (Test-MatEndpoint $endpoint)) {
  if ($override -ne "1") {
    Refuse "restore bucket/endpoint looks like MAT/local MinIO default (bucket='$bucket')."
  }
  Write-Warning "${ScriptName}: OVERRIDE_MAT_SAFETY=1 set; still prefer disposable targets."
}

if (-not (Test-LooksDisposable $bucket) -and -not (Test-LooksDisposable $backupPath)) {
  if ($override -ne "1") {
    Refuse "bucket/path does not look disposable (include disposable|drill|tmp)."
  }
}

Write-Host ("{0}: STUB - would restore {1} into s3://{2} at {3}" -f $ScriptName, $backupPath, $bucket, $endpoint)
Write-Host ("{0}: NEVER overwrite founder MAT object volumes." -f $ScriptName)
exit 0

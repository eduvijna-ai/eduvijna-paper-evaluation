# SAFE STUB: backup disposable S3-compatible object storage only.
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

$override = [Environment]::GetEnvironmentVariable("OVERRIDE_MAT_SAFETY")
if ((Test-MatBucket $bucket) -or (Test-MatEndpoint $endpoint)) {
  if ($override -ne "1") {
    Refuse "object-storage target looks like MAT/local MinIO default (bucket='$bucket' endpoint='$endpoint')."
  }
  Write-Warning "${ScriptName}: OVERRIDE_MAT_SAFETY=1 set; still prefer disposable bucket/endpoint."
}

if (-not (Test-LooksDisposable $bucket) -and -not (Test-LooksDisposable $backupPath)) {
  if ($override -ne "1") {
    Refuse "bucket/path does not look disposable (include disposable|drill|tmp)."
  }
}

Write-Host ("{0}: STUB - would sync s3://{1} from {2} to {3}" -f $ScriptName, $bucket, $endpoint, $backupPath)
Write-Host ("{0}: Use aws CLI or compatible tool against DISPOSABLE_* only." -f $ScriptName)
exit 0

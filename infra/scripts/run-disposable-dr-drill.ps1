# Real isolated DR drill: disposable Postgres + MinIO only.
# NEVER touches founder MAT ports 15432/19000 or volumes.
# Usage (from repo root):
#   powershell -NoProfile -ExecutionPolicy Bypass -File infra/scripts/run-disposable-dr-drill.ps1
$ErrorActionPreference = "Stop"
$ScriptName = Split-Path -Leaf $PSCommandPath
$RepoRoot = (Resolve-Path (Join-Path (Split-Path -Parent $PSCommandPath) "../..")).Path
$Stamp = Get-Date -Format "yyyyMMddHHmmss"
$BackupRoot = Join-Path $env:TEMP "eduvijna-dr-drill-$Stamp"
$PgDumpPath = Join-Path $BackupRoot "postgres.dump"
$ObjBackupPath = Join-Path $BackupRoot "object-storage"
$EvidencePath = Join-Path $BackupRoot "EVIDENCE.txt"
$LocalObjectFile = Join-Path $BackupRoot "paper-page-1.bin"

$PgName = "eduvijna-disposable-drill-pg"
$MinioName = "eduvijna-disposable-drill-minio"
$Network = "eduvijna-disposable-drill-net"
$PgVolume = "eduvijna_disposable_drill_pgdata"
$MinioVolume = "eduvijna_disposable_drill_miniodata"
$PgHostPort = 25432
$MinioHostPort = 29000
$DbName = "eduvijna_disposable_drill"
$DbUser = "drill_user"
$DbPass = "drill_pass_disposable_only"
$Bucket = "eduvijna-disposable-drill"
$MinioUser = "drillminio"
$MinioPass = "drillminio_disposable"
$ObjectKey = "synthetic/paper-page-1.bin"
$ObjectPayload = "SYNTHETIC-DRILL-OBJECT-$Stamp"
$RowMarker = "drill-row-$Stamp"
$AwsImage = "amazon/aws-cli:2.27.50"
$MinioImage = "bitnamilegacy/minio:2025.7.23-debian-12-r5"
$PgImage = "postgres:16-alpine"

function Write-Evidence([string]$Line) {
  Add-Content -Path $EvidencePath -Value $Line
  Write-Host $Line
}

function Remove-Disposable {
  $prev = $ErrorActionPreference
  $ErrorActionPreference = "Continue"
  foreach ($n in @($MinioName, $PgName)) {
    cmd /c "docker rm -f $n >nul 2>&1"
  }
  cmd /c "docker network rm $Network >nul 2>&1"
  cmd /c "docker volume rm $PgVolume >nul 2>&1"
  cmd /c "docker volume rm $MinioVolume >nul 2>&1"
  $ErrorActionPreference = $prev
}

function Wait-MinioReady {
  for ($i = 0; $i -lt 40; $i++) {
    docker run --rm --network $Network `
      -e AWS_ACCESS_KEY_ID=$MinioUser `
      -e AWS_SECRET_ACCESS_KEY=$MinioPass `
      -e AWS_DEFAULT_REGION=us-east-1 `
      $AwsImage s3 ls --endpoint-url "http://${MinioName}:9000" 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { return $true }
    Start-Sleep -Seconds 3
  }
  return $false
}

if ($PgHostPort -eq 15432 -or $MinioHostPort -eq 19000) {
  throw "${ScriptName}: REFUSED: refused to use MAT default ports"
}

New-Item -ItemType Directory -Force -Path $ObjBackupPath | Out-Null
Set-Content -Path $EvidencePath -Value "EduVijna disposable DR drill evidence"
Set-Content -Path $LocalObjectFile -Value $ObjectPayload -NoNewline
Write-Evidence "started_at_utc=$([DateTime]::UtcNow.ToString('o'))"
Write-Evidence "backup_root=$BackupRoot"
Write-Evidence "mat_ports_untouched=15432,19000"
Write-Evidence "disposable_ports=$PgHostPort,$MinioHostPort"

Write-Host "${ScriptName}: cleaning any prior disposable drill containers (not MAT)..."
Remove-Disposable

Write-Host "${ScriptName}: creating disposable network + postgres + minio..."
docker network create $Network | Out-Null
docker volume create $PgVolume | Out-Null
docker volume create $MinioVolume | Out-Null

docker run -d --name $PgName --network $Network `
  -e POSTGRES_DB=$DbName -e POSTGRES_USER=$DbUser -e POSTGRES_PASSWORD=$DbPass `
  -p "${PgHostPort}:5432" -v "${PgVolume}:/var/lib/postgresql/data" `
  $PgImage | Out-Null

docker run -d --name $MinioName --network $Network `
  -e MINIO_ROOT_USER=$MinioUser -e MINIO_ROOT_PASSWORD=$MinioPass `
  -p "${MinioHostPort}:9000" -v "${MinioVolume}:/bitnami/minio/data" `
  $MinioImage | Out-Null

Write-Host "${ScriptName}: waiting for disposable postgres..."
$ready = $false
for ($i = 0; $i -lt 40; $i++) {
  docker exec $PgName pg_isready -U $DbUser -d $DbName 2>$null | Out-Null
  if ($LASTEXITCODE -eq 0) { $ready = $true; break }
  Start-Sleep -Seconds 2
}
if (-not $ready) { throw "${ScriptName}: disposable postgres not ready" }

Write-Host "${ScriptName}: seeding synthetic schema/rows..."
$seedSql = @"
CREATE TABLE IF NOT EXISTS drill_tenants (
  id SERIAL PRIMARY KEY,
  slug TEXT NOT NULL UNIQUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS drill_submissions (
  id SERIAL PRIMARY KEY,
  tenant_id INT NOT NULL REFERENCES drill_tenants(id),
  object_key TEXT NOT NULL,
  marker TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
INSERT INTO drill_tenants (slug) VALUES ('disposable-tenant-$Stamp');
INSERT INTO drill_submissions (tenant_id, object_key, marker)
SELECT id, '$ObjectKey', '$RowMarker' FROM drill_tenants WHERE slug = 'disposable-tenant-$Stamp';
"@
$seedSql | docker exec -i $PgName psql -U $DbUser -d $DbName | Out-Null

$beforeCount = (docker exec $PgName psql -U $DbUser -d $DbName -tAc "SELECT count(*) FROM drill_submissions WHERE marker='$RowMarker'").Trim()
Write-Evidence "pre_backup_row_count=$beforeCount"
if ($beforeCount -ne "1") { throw "${ScriptName}: expected 1 seeded row, got $beforeCount" }

Write-Host "${ScriptName}: waiting for disposable minio then seeding object..."
if (-not (Wait-MinioReady)) {
  docker logs $MinioName 2>&1 | Select-Object -Last 40
  throw "${ScriptName}: disposable minio not ready"
}

docker run --rm --network $Network `
  -e AWS_ACCESS_KEY_ID=$MinioUser -e AWS_SECRET_ACCESS_KEY=$MinioPass -e AWS_DEFAULT_REGION=us-east-1 `
  $AwsImage s3 mb "s3://$Bucket" --endpoint-url "http://${MinioName}:9000"
if ($LASTEXITCODE -ne 0) { throw "${ScriptName}: s3 mb failed" }

docker run --rm --network $Network `
  -e AWS_ACCESS_KEY_ID=$MinioUser -e AWS_SECRET_ACCESS_KEY=$MinioPass -e AWS_DEFAULT_REGION=us-east-1 `
  -v "${LocalObjectFile}:/tmp/paper-page-1.bin:ro" `
  $AwsImage s3 cp /tmp/paper-page-1.bin "s3://$Bucket/$ObjectKey" --endpoint-url "http://${MinioName}:9000"
if ($LASTEXITCODE -ne 0) { throw "${ScriptName}: object seed failed" }
Write-Evidence "object_seeded=$ObjectKey"

Write-Host "${ScriptName}: backup postgres (pg_dump custom)..."
docker exec $PgName pg_dump -U $DbUser -d $DbName -Fc -f /tmp/postgres.dump
docker cp "${PgName}:/tmp/postgres.dump" $PgDumpPath
if (-not (Test-Path $PgDumpPath)) { throw "${ScriptName}: pg dump missing" }
Write-Evidence "postgres_dump_bytes=$((Get-Item $PgDumpPath).Length)"

Write-Host "${ScriptName}: backup object storage (aws s3 sync)..."
docker run --rm --network $Network `
  -e AWS_ACCESS_KEY_ID=$MinioUser -e AWS_SECRET_ACCESS_KEY=$MinioPass -e AWS_DEFAULT_REGION=us-east-1 `
  -v "${ObjBackupPath}:/backup" `
  $AwsImage s3 sync "s3://$Bucket" /backup --endpoint-url "http://${MinioName}:9000"
if ($LASTEXITCODE -ne 0) { throw "${ScriptName}: object backup sync failed" }
$backedFiles = @(Get-ChildItem -Path $ObjBackupPath -Recurse -File)
Write-Evidence "object_backup_file_count=$($backedFiles.Count)"
if ($backedFiles.Count -lt 1) { throw "${ScriptName}: object backup empty" }

Write-Host "${ScriptName}: intentionally destroy disposable instances (NOT MAT)..."
docker rm -f $PgName $MinioName 2>$null | Out-Null
docker volume rm $PgVolume $MinioVolume 2>$null | Out-Null
Write-Evidence "disposable_destroyed=yes"

Write-Host "${ScriptName}: recreate empty disposable postgres + minio and restore..."
docker volume create $PgVolume | Out-Null
docker volume create $MinioVolume | Out-Null
docker run -d --name $PgName --network $Network `
  -e POSTGRES_DB=$DbName -e POSTGRES_USER=$DbUser -e POSTGRES_PASSWORD=$DbPass `
  -p "${PgHostPort}:5432" -v "${PgVolume}:/var/lib/postgresql/data" `
  $PgImage | Out-Null
docker run -d --name $MinioName --network $Network `
  -e MINIO_ROOT_USER=$MinioUser -e MINIO_ROOT_PASSWORD=$MinioPass `
  -p "${MinioHostPort}:9000" -v "${MinioVolume}:/bitnami/minio/data" `
  $MinioImage | Out-Null

$ready = $false
for ($i = 0; $i -lt 40; $i++) {
  docker exec $PgName pg_isready -U $DbUser -d $DbName 2>$null | Out-Null
  if ($LASTEXITCODE -eq 0) { $ready = $true; break }
  Start-Sleep -Seconds 2
}
if (-not $ready) { throw "${ScriptName}: disposable postgres not ready after recreate" }

docker cp $PgDumpPath "${PgName}:/tmp/postgres.dump"
docker exec $PgName pg_restore -U $DbUser -d $DbName --clean --if-exists /tmp/postgres.dump
$afterCount = (docker exec $PgName psql -U $DbUser -d $DbName -tAc "SELECT count(*) FROM drill_submissions WHERE marker='$RowMarker'").Trim()
$fkOk = (docker exec $PgName psql -U $DbUser -d $DbName -tAc "SELECT count(*) FROM drill_submissions s JOIN drill_tenants t ON t.id=s.tenant_id WHERE s.marker='$RowMarker'").Trim()
Write-Evidence "post_restore_row_count=$afterCount"
Write-Evidence "post_restore_fk_join_count=$fkOk"
if ($afterCount -ne "1" -or $fkOk -ne "1") {
  throw "${ScriptName}: restore verification failed rows=$afterCount fk=$fkOk"
}

if (-not (Wait-MinioReady)) { throw "${ScriptName}: minio not ready for restore" }
docker run --rm --network $Network `
  -e AWS_ACCESS_KEY_ID=$MinioUser -e AWS_SECRET_ACCESS_KEY=$MinioPass -e AWS_DEFAULT_REGION=us-east-1 `
  $AwsImage s3 mb "s3://$Bucket" --endpoint-url "http://${MinioName}:9000" 2>$null | Out-Null

docker run --rm --network $Network `
  -e AWS_ACCESS_KEY_ID=$MinioUser -e AWS_SECRET_ACCESS_KEY=$MinioPass -e AWS_DEFAULT_REGION=us-east-1 `
  -v "${ObjBackupPath}:/backup" `
  $AwsImage s3 sync /backup "s3://$Bucket" --endpoint-url "http://${MinioName}:9000"
if ($LASTEXITCODE -ne 0) { throw "${ScriptName}: object restore sync failed" }

docker run --rm --network $Network `
  -e AWS_ACCESS_KEY_ID=$MinioUser -e AWS_SECRET_ACCESS_KEY=$MinioPass -e AWS_DEFAULT_REGION=us-east-1 `
  -v "${BackupRoot}:/out" `
  $AwsImage s3 cp "s3://$Bucket/$ObjectKey" /out/restored-paper-page-1.bin --endpoint-url "http://${MinioName}:9000"
if ($LASTEXITCODE -ne 0) { throw "${ScriptName}: object get after restore failed" }
$RestoredLocal = Join-Path $BackupRoot "restored-paper-page-1.bin"
$restoredText = (Get-Content -Raw $RestoredLocal).Trim()
$payloadMatch = ($restoredText -eq $ObjectPayload)
Write-Evidence "restored_object_payload_match=$payloadMatch"
if (-not $payloadMatch) {
  throw "${ScriptName}: object restore payload mismatch: got [$restoredText]"
}

$matPg = docker ps --filter "name=eduvijna-paper-evaluation-postgres-1" --format "{{.Status}}"
$matMinio = docker ps --filter "name=eduvijna-paper-evaluation-minio-1" --format "{{.Status}}"
Write-Evidence "mat_postgres_status=$matPg"
Write-Evidence "mat_minio_status=$matMinio"

Write-Evidence "postgres_restore=PASS"
Write-Evidence "object_storage_restore=PASS"
Write-Evidence "mat_compose_untouched=PASS"
Write-Evidence "finished_at_utc=$([DateTime]::UtcNow.ToString('o'))"
Write-Evidence "RESULT=PASS"

Write-Host "${ScriptName}: tearing down disposable resources only..."
Remove-Disposable

$DocsEvidence = Join-Path $RepoRoot "docs/production/evidence"
New-Item -ItemType Directory -Force -Path $DocsEvidence | Out-Null
$Dest = Join-Path $DocsEvidence "DR_DRILL_$Stamp.txt"
Copy-Item $EvidencePath $Dest
Write-Host "${ScriptName}: PASS - evidence at $Dest"
Write-Host "${ScriptName}: local temp artifacts at $BackupRoot (not committed)"
exit 0

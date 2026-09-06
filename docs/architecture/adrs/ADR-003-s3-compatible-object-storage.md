# ADR-003: S3-Compatible Object Storage for Paper Artifacts

## Status: Accepted

## Date: 2026-09-04

## Context

Handwritten answer sheets arrive as PDFs or high-resolution images — often tens of megabytes per assessment batch. These files are binary, append-only from a business perspective (the original scan must never be silently altered), and unsuitable for PostgreSQL bytea columns or git version control. Teachers and reviewers also need derived artifacts: annotated PDFs with region highlights, cropped answer snippets for dispute resolution, and generated export bundles.

Production deployments will use AWS S3, Azure Blob, or equivalent. Local development must mirror production semantics without cloud credentials. The `.env.example` already configures MinIO with bucket `eduvijna-papers` and standard S3 API environment variables.

Storing papers in git would bloat the repository, leak student data into clone history, and violate immutability expectations. Binary files must never be committed.

## Decision

Use **S3-compatible object storage** for all paper-related binary artifacts:

- **Production**: Cloud provider S3 API (AWS S3, GCS with S3 interop, Azure, etc.) configured via `S3_ENDPOINT_URL`, credentials, bucket, and region environment variables.
- **Local development**: MinIO (`infra` Docker Compose service) exposing the same S3 API on port 9000 with console on 9001.
- **Stored object classes**:
  - **Raw source papers** — immutable originals as uploaded (see ADR-009).
  - **Annotated PDFs / overlay renders** — derived views; originals remain untouched.
  - **Page extracts and thumbnails** — generated during structure analysis.
  - **Export artifacts** — ZIP/PDF reports generated after human approval; may be regenerated but stored as versioned export objects.
- **Write-once semantics for originals**: Application layer rejects overwrite/delete on raw source keys. Use content-addressed keys (hash prefix + UUID) so duplicate uploads dedupe safely without mutation.
- **Metadata in Postgres, bytes in S3**: Tables store `storage_key`, `content_hash`, `mime_type`, `byte_size`, and `tenant_id`; object storage holds the blob.
- **Access control**: Pre-signed URLs or authenticated proxy download through the API — buckets are not public-read. Every presign and proxy access is logged to audit (ADR-009).
- **Git policy**: `.gitignore` excludes uploads, sample papers, and export directories. CI checks must fail if binary paper files are staged.

SDK: use `boto3` (or compatible async wrapper) with path-style addressing for MinIO and virtual-host style in cloud as configured.

## Consequences

**Positive**

- Identical code paths in local, staging, and production — only endpoint and credentials change.
- Scales storage cost independently from database size; Postgres stays lean for queryable data.
- Content-addressed keys enable integrity verification (hash on upload vs. stored ETag).
- MinIO gives developers offline-capable workflows without cloud spend.

**Negative**

- Eventual consistency and lack of cross-bucket transactions mean Postgres metadata and S3 objects can diverge on partial failure — upload flows must use outbox or two-phase patterns: record `PENDING` metadata, upload, then mark `AVAILABLE`, with garbage collection for orphans.
- Backup strategy must include both Postgres and object storage; restoring one without the other breaks references.
- Pre-signed URL expiry and CORS must be tuned for the Next.js upload/download UX.

**Operational**

- Lifecycle policies (IA/Glacier) may apply to raw papers post-retention period per institution contract — out of CVB scope but bucket design supports per-tenant key prefixes (`{tenant_id}/raw/...`).

## Alternatives Considered

| Alternative | Why rejected |
|-------------|--------------|
| **Store PDFs in PostgreSQL (bytea / large objects)** | Bloats backups and memory, poor streaming performance, mixes SoR concerns. |
| **Filesystem on API server** | Not portable across replicas, no pilot-to-prod parity, weak durability guarantees. |
| **Git LFS for sample papers** | Still couples binary data to repo history; unacceptable for real student papers and immutability audit. |
| **Cloud-only S3 (no MinIO locally)** | Forces every developer to cloud credentials and network; slows onboarding and CI. |
| **NFS / shared volume for workers** | Breaks in multi-AZ deployment and conflicts with content-addressed immutability model. |

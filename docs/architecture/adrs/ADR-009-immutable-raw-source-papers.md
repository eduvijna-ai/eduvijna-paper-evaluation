# ADR-009: Immutable Raw Source Papers with Overlay Annotations

## Status: Accepted

## Date: 2026-09-04

## Context

Handwritten answer sheets are legal and pedagogical evidence. Once uploaded, the original scan must remain tamper-evident: if an annotated "marked copy" overwrites the upload, disputes cannot distinguish institution markup from student submission. EduVijna also processes sensitive minor student data — mutation or silent replacement of source files is unacceptable.

Object storage (ADR-003) holds bytes; this ADR defines **immutability semantics** and the separation between originals and derived views. Content addressing detects accidental or malicious substitution.

## Decision

Treat **original uploads as immutable**; all markup exists as **overlays** stored separately:

**Storage model**

- **Raw object** (`storage_class = RAW_SOURCE`): Written once at upload completion. S3 key is **content-addressed**: `{tenant_id}/raw/{sha256_prefix}/{uuid}.pdf` (or image extension). Metadata row in Postgres includes `content_hash`, `byte_size`, `uploaded_at`, `uploaded_by`.
- **Write-once enforcement**:
  - Application: PUT to existing raw key rejected; API returns 409 if hash collision with different metadata is detected.
  - IAM/bucket policy where possible: deny `s3:DeleteObject` and overwrite on `raw/` prefix for worker credentials; only break-glass admin role with audit.
- **Annotations as overlays**:
  - Region bounding boxes, highlight layers, reviewer notes, and "marked PDF" renders stored as separate objects: `{tenant_id}/derived/{submission_id}/annotations/{version}.json` and `{tenant_id}/derived/.../marked_{version}.pdf`.
  - Marked PDFs are **rendered composites** (original bytes + overlay instructions) — never replace the raw key.
  - Annotation versions increment; latest used for UI default; historical versions retained for audit.

**Integrity**

- On upload, compute SHA-256 stream hash; verify against stored hash on every worker read before AI processing.
- ETag/hash mismatch triggers `audit_events` entry with severity `INTEGRITY_FAILURE` and blocks pipeline progression.

**Access audit**

- Log to `audit_events`: raw object presign issued, proxy download, failed mutation attempt, break-glass admin access.
- Fields: `tenant_id`, `actor_id`, `source_paper_id`, `action`, `ip`, `outcome`.

**Git and developer machines**

- Sample papers for tests use synthetic fixtures in CI-generated temp dirs, not committed binaries (ADR-003 git policy).
- Production-like dumps never committed.

**UI behavior**

- Reviewer sees overlay on original viewer layer; "download original" always fetches raw key; "download marked copy" fetches derived composite only.

## Consequences

**Positive**

- Clear chain of custody for appeals: original unchanged, annotations versioned.
- Content addressing enables deduplication when same file uploaded twice (same hash, new metadata row optional).
- Integrity checks catch storage corruption or mis-keyed objects early.

**Negative**

- Marked PDF generation is a render step (CPU/storage cost) rather than in-place edit.
- Storage grows with annotation versions; lifecycle policies may archive old derived objects while retaining raw per retention policy.
- Break-glass overwrite requires operational procedure and dual control — intentional friction.

**Worker contract**

Pipeline tasks receive `raw_storage_key` + hash; they must not write to raw prefix. All outputs go to `derived/` or Postgres.

## Alternatives Considered

| Alternative | Why rejected |
|-------------|--------------|
| **Mutable S3 object per submission** | Cannot prove original unchanged after review edits. |
| **Store annotated PDF as new "original"** | Conflates evidence layers; audit trail collapses. |
| **Immutability via DB flag only** | Without storage-level deny, compromised credentials can still overwrite blobs. |
| **WORM legal hold only in cloud** | Needed for enterprise later; application semantics required regardless of vendor WORM. |
| **Blockchain hash anchoring** | Overkill for CVB; SHA-256 + audit sufficient for pilot trust model. |

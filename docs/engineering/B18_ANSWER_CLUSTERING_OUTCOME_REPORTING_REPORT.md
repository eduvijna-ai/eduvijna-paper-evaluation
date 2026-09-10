# B18 — Answer Clustering & CO/PO Outcome Reporting

**Tranche:** B18  
**Approval:** APP-012 / Issue #76  
**Starting `develop` SHA:** `05104717514808a6141034eac15a21dbdd0c248e` (post APP-011)  
**Expected unchanged `main`:** `548960e6b35e5229595c9fd0ef17d9b375080e07`  
**Status:** GOVERNANCE AUTHORIZED — implementation pending  

## Scope

Activate as bounded `FUTURE_ENTERPRISE` implementation on `develop` only:

* **PEV-050** Answer Clustering — deterministic transcription-embedding clusters; authorized reviewer inspection; advisory rubric-refinement observations only.
* **PEV-051** CO / PO Reporting — tenant-scoped outcome definitions; versioned question→outcome mapping sets; marks-weighted attainment report snapshots with JSON + CSV export.

## Classification

* PEV-050 remains **FUTURE_ENTERPRISE** (implementation does not change release-state classification).
* PEV-051 remains **FUTURE_ENTERPRISE**.

## Deferred (not in APP-012)

PEV-054, PEV-055, PEV-056, PEV-057.

PEV-048/049 already released through APP-011 — do not redesign.

## Architectural invariants

* Source-of-truth chain unchanged: immutable source evidence → structured understanding → rubric decisions → evaluation ledger → human approval → published result → analytics / learning evidence.
* Evaluation ledger remains authoritative for scores.
* Only current effective `PUBLISHED` results participate in current analytics; `SUPERSEDED` must not double-count.
* Clustering must never automatically mutate, approve, or activate a rubric.
* CO/PO analytics must never rewrite historical evaluation results.
* Tenant isolation on every service/query boundary.
* No main promotion under APP-012.
* No external vector database, pgvector requirement, Kubernetes, Temporal, Kafka, GraphQL, microservices split, Firebase, Supabase, or serverless-only redesign.

## Planned surfaces (implementation)

* Migration: `20260910_0019_b18_answer_clustering_outcome_reporting` (down_revision `20260910_0018`).
* Deterministic embedding provider (credential-free fixed for CI) + `COSINE_GRAPH_V1` clustering.
* Outcome definitions, immutable ACTIVE mapping sets, attainment report snapshots + CSV.
* Narrow permissions: `clustering:*`, `outcomes:*`.
* Frontend quality/outcomes operator screens + Vitest + mock E2E + real `zz-b18` Playwright gate.

## Explicit non-goals

* No main release / exact-tree promotion.
* No SSO/SCIM, LMS/LTI, multi-subject, or multilingual handwriting.
* No automatic rubric mutation from cluster review.
* No LLM-based attainment calculation.

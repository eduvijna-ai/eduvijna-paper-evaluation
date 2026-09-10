# B18 — Answer Clustering & CO/PO Outcome Reporting

**Tranche:** B18  
**Approval:** APP-012 / Issue #76  
**Implementation Issue:** B18 / Issue #78  
**Starting `develop` SHA:** `7849afcb71bf84afa8e6f87a181e9cbdca7d6c09` (post APP-012 governance)  
**Expected unchanged `main`:** do not promote under APP-012  
**Status:** Implemented on `develop` (FUTURE_ENTERPRISE release-state classification unchanged)

## Scope delivered

* **PEV-050** Answer Clustering — deterministic transcription-embedding clusters (`COSINE_GRAPH_V1`); authorized reviewer inspection; advisory rubric-refinement observations only (never mutates rubric / QE / ReviewAction / PublishedResult).
* **PEV-051** CO / PO Reporting — tenant-scoped outcome definitions; versioned question→outcome mapping sets (ACTIVE immutable); marks-weighted attainment report snapshots with JSON + CSV export.

## Classification

* PEV-050 remains **FUTURE_ENTERPRISE** (implementation does not change release-state classification).
* PEV-051 remains **FUTURE_ENTERPRISE**.

## Surfaces

| Layer | Path / artifact |
| --- | --- |
| Migration | `database/migrations/versions/20260910_0019_b18_answer_clustering_outcome_reporting.py` (rev `20260910_0019`, down `20260910_0018`) |
| Models | `apps/api/app/db/models/outcome_intelligence.py` |
| Embedding | `FixedEmbeddingProvider` via `get_embedding_provider()` (reuses `AI_PROVIDER_TEXT`; credential-free fixed for CI) |
| Clustering math | `apps/api/app/services/cluster_math.py` |
| Service | `apps/api/app/services/outcome_intelligence.py` |
| API | `apps/api/app/api/v1/outcome_intelligence.py` |
| Permissions | `clustering:read\|manage\|review`, `outcomes:read\|manage\|report` |
| Seed | `apps/api/app/cli/seed_b18_e2e_outcome_intelligence.py` (`B18-E2E-OUTCOME`) |
| Backend tests | `apps/api/tests/test_b18_answer_clustering.py`, `test_b18_outcome_reporting.py` |
| Frontend | `/quality/clustering`, `/outcomes/reporting` |
| E2E | `apps/web/e2e/b18-outcome-intelligence.spec.ts`, `apps/web/e2e/real/zz-b18-outcome-intelligence.spec.ts` |
| Contracts | `packages/contracts/schemas/*`, OpenAPI paths under `/quality/answer-clusters/*` and `/outcomes/*` |

## Invariants preserved

* Only current effective `PUBLISHED` results; `SUPERSEDED` excluded.
* Historical cluster runs / attainment reports immutable (idempotent by cohort fingerprint).
* Cluster review advisory only.
* ACTIVE mapping sets immutable; new version for changes.
* Exact marks-weighted attainment: `pct = 100 * SUM(score*weight) / SUM(max*weight)`; `ZERO_DENOM` when max is 0.
* No vector DB / pgvector / K8s / Kafka / Temporal / GraphQL / microservices.
* No `main` promotion under APP-012.

## Deferred (not in APP-012)

PEV-054, PEV-055, PEV-056, PEV-057.

---

## APP-013 release approval (promotion only)

**Issue:** #84  
**Decision:** Founder approves promotion of independently accepted APP-012 / B18 + B18.1 + B18.2 (PEV-050–051) from `develop` to `main`.  
**Status:** APPROVED  
**Milestone:** Answer Intelligence & Outcome Reporting Release / APP-013  

**Traceability:** APP-012 Issue #76; B18 Issue #78 / PR #79; B18.1 Issue #80 / PR #81; B18.2 Issue #82 / PR #83  

Starting develop (pre-governance): `4148401549591472453f1bf7231727921352937e`  
Starting develop tree: `b5049642fc0e094171da2bb6bbe662357856fa7a`  
Expected main until promotion: `548960e6b35e5229595c9fd0ef17d9b375080e07`  
Expected main tree until promotion: `286897f47943bf265cf1ce3e66d0d4d49a650ada`  

Release promotion only — no new implementation; classifications remain `FUTURE_ENTERPRISE`; PEV-054–057 remain deferred; exact-tree snapshot mandatory (main/develop histories intentionally diverge); no direct develop→main conflict resolution; no merge-back from main to develop; no AI provider/model deployment authorization; no migration beyond already accepted `20260910_0019` and corrected `20260910_0020`.

Final release SHAs are recorded after governance squash and main promotion (not invented here).

# B11 — CVB release audit blocker fixes

**Branch:** `b11/cvb-release-blocker-fixes`  
**PR base:** `develop`  
**Starting `develop` SHA:** `be73cc3bcf91b4078b3fea63b3788403129a1419`  
**Starting `main` SHA:** `be5f10aef3cf536420adcffdb9302b6b3b6c0955`  
**Migration:** none (application-logic + contract/test fixes; no schema change required)  
**Final feature SHA:** `7be4005001c07785022e4e09aeeef2b79b377ace`  
**CI run ID:** `34128113727`  
**Squash SHA:** `dd6bd64faf7ddcd089c94d7c32f748ec70109840`  
**Final `develop` after B11:** `dd6bd64faf7ddcd089c94d7c32f748ec70109840`  
**Final `main` after B11:** `be5f10aef3cf536420adcffdb9302b6b3b6c0955` (unchanged)  
**Release approval:** `APP-002` in `docs/FOUNDER_APPROVAL_LOG.md`

## Independent post-B10 defects closed

| Blocker | Defect | Fix |
|---------|--------|-----|
| A | Parse used metadata-only `QuestionPaperParseInput`; tests parsed without upload | Require `AssessmentArtifact`; load bytes; PyMuPDF/image evidence; evidence-dependent fixed provider |
| B | Curriculum suggest auto-wrote `QuestionCurriculumMapping` | Proposal-only worker + human `apply-curriculum-mappings` |
| C | Provider node IDs not allowlisted | Strict candidate-set validation; reject foreign/unknown IDs |
| D | Incomplete PEV-060 `model` / `model_version` / `prompt_template_version` | `AIExecutionMetadata` + provider `execution_metadata()` on actual invocations |

## Question-paper evidence (PEV-002)

* `409 QUESTION_PAPER_ARTIFACT_REQUIRED` when no linked artifact  
* Integrity: storage exists + SHA-256 + byte size  
* Bounds: `AUTHORING_PARSE_MAX_PAGES` (30), text/page/image/pixel caps  
* PDF: text extract; render bounded PNG when text insufficient  
* PNG/JPEG: bounded decode → visual evidence  
* Fixed provider derives prompt/label from extracted text (fails if empty)  
* OpenAI adapter sends page text / multimodal images (mocked in CI)

## Curriculum mapping human gate

* Suggest → `REVIEW_REQUIRED` proposal only  
* `PUT .../curriculum-mapping-proposal` edits within candidate allowlist  
* `POST .../apply-curriculum-mappings` creates canonical rows + audit + `SUCCEEDED`  
* Idempotent re-apply

## PEV-060

* `app/ai/execution_metadata.py`  
* Fixed/OpenAI providers expose truthful metadata  
* Authoring + structure/transcription/evaluation/publication/learning call sites updated

## Tests

* `apps/api/tests/test_b11_release_blockers.py`  
* Updated B10 authoring tests to upload real PDFs  
* Frontend `b11-curriculum.test.ts`  
* Real E2E asserts source-derived prompt + curriculum apply UI

## Verification

* Backend pytest: **163 passed**  
* Frontend Vitest: **155 passed** (31 files)  
* Mock E2E: **15 passed**  
* Real E2E: **11 passed**  
* GitHub Actions run `34128113727`: Infrastructure / Contracts / Backend / Frontend / Frontend E2E / Frontend E2E Real = **SUCCESS** on exact feature SHA `7be4005001c07785022e4e09aeeef2b79b377ace`  
* BUILD_NOW: **59 VERIFIED / 0 BLOCKED**

## BUILD_NOW

See `CVB_BUILD_NOW_RELEASE_AUDIT.md` — post-B10 findings recorded; re-verified after B11.

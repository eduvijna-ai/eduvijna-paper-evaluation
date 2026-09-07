# B11 — CVB release audit blocker fixes

**Branch:** `b11/cvb-release-blocker-fixes`  
**PR base:** `develop`  
**Starting `develop` SHA:** `be73cc3bcf91b4078b3fea63b3788403129a1419`  
**Starting `main` SHA:** `be5f10aef3cf536420adcffdb9302b6b3b6c0955`  
**Migration:** none (application-logic + contract/test fixes; no schema change required)  
**Final feature SHA:** `_TBD_`  
**CI run ID:** `_TBD_`  
**Squash SHA:** `_TBD_`  

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

## BUILD_NOW

See `CVB_BUILD_NOW_RELEASE_AUDIT.md` — post-B10 findings recorded; re-verified after B11.

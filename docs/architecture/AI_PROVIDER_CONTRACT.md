# AI Provider Contract

**Product:** EduVijna Paper Evaluation (CVB v0.1)  
**Package:** `apps/api/app/ai/` (runtime); architecture stub under `ai/`  
**Last updated:** 2026-09-18  
**Related:** [ADR-007](adrs/ADR-007-ai-provider-abstraction.md), [EVALUATION_LEDGER.md](./EVALUATION_LEDGER.md), [SECURITY_BASELINE.md](./SECURITY_BASELINE.md)

---

## 1. Purpose

All AI capabilities are invoked through **named, typed operations** behind Python Protocol/ABC interfaces. Vendor SDKs live in provider adapters only. The **frontend never calls AI providers** — all paths go API → Celery worker → `ai` module.

Every invocation produces an **`AiExecutionRecord`** in PostgreSQL for traceability, cost attribution, and confidence dimension derivation.

---

## 2. Architecture

```
┌─────────────┐     ┌─────────────┐     ┌──────────────────┐
│  apps/web   │────▶│  apps/api   │────▶│  workers (Celery)│
│  (Cursor B) │     │  FastAPI    │     │  pipeline tasks  │
└─────────────┘     └─────────────┘     └────────┬─────────┘
                                                  │
                                                  ▼
                                         ┌──────────────────┐
                                         │  ai/protocols.py │
                                         │  ai/registry.py  │
                                         └────────┬─────────┘
                                                  │
                              ┌───────────────────┼───────────────────┐
                              ▼                   ▼                   ▼
                       OpenAI adapter      Anthropic adapter    Mock (tests)
```

---

## 3. Operation Interfaces

Each B5 operation defines typed Pydantic models in `apps/api/app/ai/types.py`.

### Implemented in B20 (multi-subject & multilingual understanding — PEV-056 / PEV-057 / APP-017 / Issue #107)

Formal release state remains **FUTURE_ENTERPRISE**. B20 implements the understanding-layer expansion without a second grading pipeline.

* Canonical subject remains `Assessment.subject_node_id` (CurriculumNode projection). No independent Subject table.
* Bounded subject profiles: `MATHEMATICS`, `PHYSICS`, `CHEMISTRY`, `STATISTICS`, `ACCOUNTING`, `STRUCTURED_DESCRIPTIVE`, plus `UNSPECIFIED` (legacy missing `subject_node_id` only) and `UNSUPPORTED` (fail-closed for present unknown nodes, unresolved node IDs, and invalid metadata). Unknown configured subjects never silently become Mathematics.
* `verify_math` / SymPy remains Mathematics-compatible only (`MATHEMATICS` and genuine legacy `UNSPECIFIED`). Physics/Chemistry/descriptive/accounting/statistics and any present unknown subject do not enter the Math-only verification path.
* Submission language/script is persisted (BCP-47 / ISO-15924 subset). States: `UNKNOWN` | `CONFIRMED` | `REVIEW_REQUIRED` | `UNSUPPORTED`.
* Original-language transcription is authoritative. Translation/transliteration is a derived artifact (`TranscriptionDerivedText`) linked to the exact original transcription version; it never overwrites `AnswerRegionTranscription.text`.
* Typed requests (`TranscriptionInput`, `RubricEvaluationInput`) carry resolved subject profile, language, script, and derived-text provenance. Evaluation `transcription_text` remains original evidence.
* Provider capability routing is a deterministic subject × language × script × operation matrix (`app/ai/capability.py`). Unsupported combinations fail closed with stable codes (`SUBJECT_PROFILE_UNSUPPORTED`, `LANGUAGE_UNSUPPORTED`, `SCRIPT_UNSUPPORTED`, `LANGUAGE_REVIEW_REQUIRED`, `LANGUAGE_CONTEXT_REQUIRED`, `LANGUAGE_CONTEXT_LOCKED`).
* `AiExecutionRecord` stores redacted routing metadata (profile/language/script/operation/provider/model) — never raw answer-sheet content.
* Fixed/local provider covers B20 fixtures (Mathematics, Physics, Chemistry, descriptive/accounting/statistics, Hindi+Devanagari with translation/transliteration, unsupported language/script). Mandatory CI remains credential-free.
* B15 isolated replay fixtures may carry B20 context. Regression still cannot mutate ledger, publication, review, mastery, or learning evidence.

### Implemented in B15 (gold benchmark / AI regression — PEV-058 / PEV-059)

* Gold dataset curation remains human-adjudicated and tenant-scoped (PEV-058).
* Isolated regression against locked gold versions (PEV-059) via:

  | Path | When | Credentials |
  |------|------|-------------|
  | **CI fixtures** | `candidate_provider=fixed` and model ∈ `fixed-benchmark-pass` / `fixed-benchmark-regress` / `fixed-benchmark-invalid` | Never required |
  | **Configured production candidate** | `candidate_provider` matches the active `AI_PROVIDER_VISION` evaluation provider (`fixed` or `openai`) and model is **not** a CI fixture name | Uses configured runtime credentials when provider is `openai`; mandatory GitHub CI still uses fixtures / fixed only |

Configured candidates resolve exclusively through `get_evaluation_provider()` / `get_benchmark_candidate_executor()` and call `evaluate_rubric` on a frozen PII-minimized replay fixture. Results are written only to `benchmark_regression_*` tables and `AiExecutionRecord` — never to `QuestionEvaluation`, criterion ledger rows, `PublishedResult`, review actions, or B8/B12/B14 mastery state. Release gate APIs/CLI determine eligibility only; they do **not** deploy providers or models.

### Implemented in B10 (authoring)

* `parse_question_paper`
* `propose_answer_key`
* `propose_rubric`
* `suggest_curriculum_mapping`

Provider modes: `AI_PROVIDER_AUTHORING` = `none` | `fixed` (test/dev only) | `openai`.  
Proposals never mutate evaluation marks; teacher approve gates remain mandatory (PEV-004).

### Implemented in B5

* `extract_student_identity`
* `analyze_page`
* `map_answer_regions`
* `transcribe_answer`

Provider modes: `none` | `fixed` (test/dev only) | `openai` (optional).

### Implemented in B6+

* `evaluate_rubric`
* `verify_math` (SymPy, in-process — not on the provider Protocol)
* `classify_error`

The structure provider must never publish or mutate marks.

### 3.1 `extract_student_identity`

**Stage:** Submission processing — identity  
**Input:** Cover page image S3 ref, optional roster hints  
**Output:**

```python
@dataclass
class IdentityExtractionResult:
    extracted_name: str | None
    extracted_roll: str | None
    extracted_class: str | None
    candidate_student_ids: list[UUID]  # roster matches
    identity_confidence: Decimal
    raw_fields: dict
```

**Confidence:** Feeds `identity_confidence` on ledger.

---

### 3.2 `analyze_page`

**Stage:** Structure — layout  
**Input:** Page image S3 ref, assessment version context  
**Output:** Printed question numbers, handwriting zones, table/diagram detection, page metadata.

---

### 3.3 `map_answer_regions`

**Stage:** Structure — mapping  
**Input:** Page analysis, assessment question tree, region bboxes  
**Output:**

```python
@dataclass
class RegionMappingResult:
    mappings: list[QuestionRegionMapping]  # question_id, region_ids, confidence
    mapping_confidence: Decimal
    unmapped_regions: list[UUID]
```

**Confidence:** Feeds `mapping_confidence`.

---

### 3.4 `transcribe_answer`

**Stage:** Structure — transcription  
**Input:** Cropped answer region S3 ref, question type, **resolved subject profile, language code, script code, language state**  
**Output:**

```python
class TranscriptionResult:
    text: str                    # original-language text only
    latex: str | None
    segments: list[TranscriptionSegment]
    transcription_confidence: Decimal
    unreadable: bool
    derived_texts: list[DerivedTextProposal]  # translation/transliteration; never replaces text
```

Capability check (`transcribe_answer` × subject × language × script) runs before the provider. Unsupported combinations fail closed and do not invoke a generic Math/English fallback.

---

### 3.5 `evaluate_rubric`

**Stage:** Evaluation — rubric application  
**Input:** Frozen `RubricVersion`, `AnswerKeyVersion`, **original** transcription text, optional derived-text provenance (`original_transcription_id`, `derived_text`, source/target language). Translated text is never presented as original evidence.  
**Output:**

```python
@dataclass
class RubricEvaluationResult:
    criterion_proposals: list[CriterionProposal]
    proposed_total: Decimal
    evaluation_confidence: Decimal
    first_divergence_step: int | None
    alternative_method_id: str | None
    ecf_applied: bool
    error_codes: list[str]
```

**Rule:** Writes **draft** ledger only; never publishes.

---

### 3.6 `verify_math`

**Stage:** Evaluation — deterministic assist  
**Implementation:** **SymPy** for symbolic equivalence; numeric tolerance from rubric  
**Input:** Transcribed expression, expected answer, `accepted_equivalent_expressions`, precision rules  
**Output:**

```python
@dataclass
class MathVerificationResult:
    equivalent: bool
    normalized_student: str
    normalized_expected: str
    math_verification_confidence: Decimal
    failure_reason: str | None
```

SymPy runs in-process — not delegated to LLM. **B20:** invocation is gated by `math_verification_allowed(subject_profile)`. Non-Mathematics profiles never enter this path even if an expression-like string is present.

---

### 3.7 `classify_error`

**Stage:** Evaluation — taxonomy  
**Input:** Transcription, criterion context, rubric criterion, divergence step  
**Output:** Ordered `error_codes` from [ERROR_TAXONOMY.md](./ERROR_TAXONOMY.md) with evidence spans.

---

### 3.8 `generate_student_explanation`

**Stage:** Reporting (post-approval)  
**Input:** **Approved** ledger snapshot IDs, rubric explanations  
**Output:** Student-facing question-by-question narrative  
**Constraint:** Must not alter marks; validator compares cited marks to ledger.  
**Status:** **Implemented in B7** via narrative provider (`AI_PROVIDER_TEXT=fixed|openai|none`) during publication generation. Traced on `AiExecutionRecord` with `published_result_id`.

---

### 3.9 `generate_parent_summary`

**Stage:** Reporting (post-approval)  
**Input:** Approved ledger + class context  
**Output:** Plain-language summary for guardians.  
**Status:** **Implemented in B7** via narrative provider during publication generation (same registry / tracing path as 3.8).

---

### 3.10 `generate_learning_plan`

**Stage:** Learning evidence (post-publication mastery evidence)  
**Input:** Server-authorized plan structure (recommendation keys, default rationales, path steps) derived from B8 `MasteryEvidence` + curriculum graph — not raw mark mutation  
**Output:** Bounded prose overlays (rationale / path descriptions). Structure remains server-owned (`B9_V1`).  
**Constraint:** No URLs; curriculum-node IDs only; no Assessment/resource invention.  
**Status:** **Implemented in B9** via `LearningAIProvider` (`AI_PROVIDER_TEXT=fixed|openai|none` → `FIXED` / `AI` / `RULES_FALLBACK`). Traced on `AiExecutionRecord` with `learning_plan_run_id`. Worker: `learning.generate_plan`.

---

### 3.11 `generate_improvement_blueprint`

**Stage:** Learning evidence (post READY learning plan)  
**Input:** Server-authorized blueprint item skeletons (template kinds, node IDs, default focus)  
**Output:** Title + item focus prose for an `ImprovementAssessment` **blueprint** (not a live Assessment).  
**Constraint:** No URLs; items must cover plan targets; no reassessment entity creation.  
**Status:** **Implemented in B9** via `LearningAIProvider` (same text-provider modes). Traced with `improvement_assessment_id` (+ `learning_plan_run_id`). Worker: `learning.generate_improvement_blueprint`.

---

### 3.12 `parse_question_paper`

**Stage:** Authoring — question paper structure  
**Input:** Assessment version context + optional `assessment_artifact` (content hash / mime / filename)  
**Output:** Bounded `ProposedQuestionNode` tree (`roots`) + notes  
**Bounds:** Max depth 6, max 200 nodes, unique `stable_code`, leaf marks must reconcile on apply  
**Status:** **Implemented in B10** via `AuthoringAIProvider` (`AI_PROVIDER_AUTHORING=fixed|openai|none`). Durable `AuthoringAiRun` (`PARSE_QUESTION_PAPER`). Teacher edit + apply required before questions exist. Contract: `question-paper-parse.schema.json`.

---

### 3.13 `propose_answer_key`

**Stage:** Authoring — answer key proposal  
**Input:** Question version prompt / marks context  
**Output:** `answer_text` (+ optional structured answer)  
**Constraint:** Creates `AnswerKeyVersion` with `source_type=AI_PROPOSED` only; evaluation blocked until teacher approve. Never overwrites teacher material.  
**Status:** **Implemented in B10** via `AuthoringAIProvider`. Traced with `authoring_ai_run_id`.

---

### 3.14 `propose_rubric`

**Stage:** Authoring — rubric proposal  
**Input:** Question (+ optional answer text)  
**Output:** Rubric title + bounded criteria list  
**Constraint:** Draft `RubricVersion` `AI_PROPOSED` enters review; not usable for evaluation until approve.  
**Status:** **Implemented in B10** via `AuthoringAIProvider`. Traced with `authoring_ai_run_id`.

---

### 3.15 `suggest_curriculum_mapping`

**Stage:** Authoring — curriculum mapping suggestion  
**Input:** Question text + candidate curriculum nodes  
**Output:** Ordered mapping suggestions (`PRIMARY` / `SECONDARY` / …)  
**Constraint:** Suggestions only; teacher applies mappings via A2 APIs.  
**Status:** **Implemented in B10** via `AuthoringAIProvider`.

---

## 4. Provider Registry

`ai/registry.py` selects adapter by:

| Config key | Example |
|------------|---------|
| `AI_PROVIDER_VISION` | `openai` |
| `AI_PROVIDER_TEXT` | `anthropic` |
| `AI_PROVIDER_CLASSIFY` | `openai` |
| `AI_PROVIDER_AUTHORING` | `fixed` / `openai` / `none` |
| Per-tenant override | `tenants.config.ai_providers` JSONB |

**No generic `complete(prompt)` exported** to domain modules — internal to adapters only.

---

## 5. AiExecutionRecord Tracing

Every operation call persists:

| Field | Source |
|-------|--------|
| `tenant_id`, `submission_id`, `evaluation_run_id` | Task context |
| `operation` | Interface name |
| `provider`, `model`, `model_version` | Adapter |
| `prompt_template_version` | Internal template semver |
| `input_refs` | S3 keys, entity UUIDs (not raw image bytes) |
| `input_hash` | SHA-256 normalized input |
| `output_summary` | Truncated structured result |
| `status`, `latency_ms`, `token_usage`, `error_class` | Runtime metrics |

Link record IDs to ledger via `ai_execution_record_ids`.

**Replay:** Disputes reproduce inputs from S3 + hash; prompts stored by template version in git, not full prompt text in DB (unless debug flag).

---

## 6. Execution Context Rules

| Operation class | When allowed | Mark mutation |
|-----------------|--------------|---------------|
| Structure (identity, map, transcribe) | Submission < `APPROVED` | No marks |
| Evaluation (`evaluate_rubric`, `verify_math`, `classify_error`) | Rubric `PUBLISHED` | Draft proposals only |
| Gold benchmark replay (`gold_benchmark_evaluate` via registry) | Locked B15 gold version | **Forbidden** for ledger / published / mastery writes |
| Narrative (`generate_student_explanation`, `generate_parent_summary`) | Submission ≥ `APPROVED` / publication | **Forbidden** |
| Learning (`generate_learning_plan`, `generate_improvement_blueprint`) | After B8 READY evidence / READY plan | **Forbidden** (structure server-owned) |
| Authoring (`parse_question_paper`, `propose_*`, `suggest_curriculum_mapping`) | Assessment academic config mutable (typically DRAFT) | **Forbidden** for evaluation marks; proposals only |

Workers set `app.tenant_id` before any DB or AI call.

---

## 7. Error Handling

| Failure | Behavior |
|---------|----------|
| Provider timeout | Retry with backoff (Celery); record `TIMEOUT` |
| Provider 429 | Rate-limit queue; record status |
| Invalid output schema | `FAILED`; submission may → `REVIEW_REQUIRED` |
| SymPy parse failure | Fall through to `evaluate_rubric` with lower `math_verification_confidence` |

---

## 8. Testing

`ai/mocks/` implements all protocols for deterministic CI. Golden fixtures in `tests/fixtures/ai/` — no live provider calls in default test suite.

---

## 9. Package Layout (Target)

```
ai/
  protocols.py          # Protocol definitions
  types.py              # Input/output dataclasses
  registry.py           # Provider selection
  tracing.py            # AiExecutionRecord writer
  providers/
    openai/
    anthropic/
  mocks/
    fixed_responses.py
```

---

## 10. Document Control

| Version | Date | Change |
|---------|------|--------|
| 0.1 | 2026-09-04 | Initial AI provider contract |
| 0.2 | 2026-09-07 | B7 narrative ops implemented |
| 0.3 | 2026-09-07 | B9 `generate_learning_plan` + `generate_improvement_blueprint` implemented |
| 0.4 | 2026-09-07 | B10 authoring ops: `parse_question_paper`, `propose_answer_key`, `propose_rubric`, `suggest_curriculum_mapping` |
| 0.5 | 2026-09-09 | B15 PEV-058/059: CI fixed fixtures + configured EvaluationAIProvider gold replay; no ledger mutation |

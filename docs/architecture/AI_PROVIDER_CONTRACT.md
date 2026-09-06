# AI Provider Contract

**Product:** EduVijna Paper Evaluation (CVB v0.1)  
**Package:** `apps/api/app/ai/` (runtime); architecture stub under `ai/`  
**Last updated:** 2026-09-06  
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

### Implemented in B5

* `extract_student_identity`
* `analyze_page`
* `map_answer_regions`
* `transcribe_answer`

Provider modes: `none` | `fixed` (test/dev only) | `openai` (optional).

### Deferred to B6+

* `evaluate_rubric`
* `verify_math`
* `classify_error`
* reporting / learning operations

The B5 provider must never publish or mutate marks.

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
**Input:** Cropped answer region S3 ref, question type (math/text)  
**Output:**

```python
@dataclass
class TranscriptionResult:
    text: str
    latex: str | None
    segments: list[TranscriptionSegment]  # step-indexed
    transcription_confidence: Decimal
    unreadable: bool  # triggers UNREADABLE taxonomy, not auto-wrong
```

---

### 3.5 `evaluate_rubric`

**Stage:** Evaluation — rubric application  
**Input:** Frozen `RubricVersion`, `AnswerKeyVersion`, transcription, rules-engine pre-checks  
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

SymPy runs in-process — not delegated to LLM.

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

---

### 3.9 `generate_parent_summary`

**Stage:** Reporting (post-approval)  
**Input:** Approved ledger + class context  
**Output:** Plain-language summary for guardians.

---

### 3.10 `generate_learning_plan`

**Stage:** Learning evidence (post-approval)  
**Input:** Approved ledger, curriculum nodes, prerequisite graph  
**Output:** Curriculum-constrained recommendations (node IDs + rationale).

---

### 3.11 `generate_improvement_blueprint`

**Stage:** Learning evidence (post-approval)  
**Input:** Weakness profile, curriculum scope  
**Output:** `ImprovementAssessment` structure with targeted practice items.

---

## 4. Provider Registry

`ai/registry.py` selects adapter by:

| Config key | Example |
|------------|---------|
| `AI_PROVIDER_VISION` | `openai` |
| `AI_PROVIDER_TEXT` | `anthropic` |
| `AI_PROVIDER_CLASSIFY` | `openai` |
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
| Narrative (`generate_*`) | Submission ≥ `APPROVED` | **Forbidden** |

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

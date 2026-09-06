# Error Taxonomy

**Product:** EduVijna Paper Evaluation (CVB v0.1)  
**Last updated:** 2026-09-04  
**Related:** [EVALUATION_LEDGER.md](./EVALUATION_LEDGER.md), [RUBRIC_SCHEMA.md](./RUBRIC_SCHEMA.md)

---

## 1. Purpose

Standardized **error codes** classify why marks were deducted or why automated processing could not complete a decision. Codes appear on ledger rows (`error_codes`), criterion decisions, and review queues.

**Critical rule:** `UNREADABLE` indicates **evidence quality**, not academic incorrectness. Unreadable work routes to human review — it is **not** automatically scored as wrong.

---

## 2. Top-Level Academic Error Categories

Used when student work is legible and evaluated against the rubric.

| Code | Label | Description | Typical mark impact |
|------|-------|-------------|---------------------|
| `CONCEPT` | Conceptual error | Fundamental misunderstanding of concept | Major deduction |
| `FORMULA` | Formula error | Wrong formula selected or recalled | Major / partial |
| `METHOD` | Method error | Invalid or inappropriate solution approach | Partial to zero |
| `CALCULATION` | Calculation error | Arithmetic slip with correct method | Partial (ECF may apply) |
| `ALGEBRA` | Algebra error | Symbolic manipulation mistake | Partial |
| `SIGN` | Sign error | Sign mistake (+/−) | Partial |
| `SUBSTITUTION` | Substitution error | Incorrect value substitution | Partial; ECF origin |
| `NOTATION` | Notation error | Non-standard or ambiguous notation | Minor / presentation |
| `UNIT` | Unit error | Missing or wrong unit | Unit marks / gate |
| `DIAGRAM` | Diagram error | Incorrect or incomplete diagram | Per rubric |
| `INTERPRETATION` | Interpretation error | Misread question or graph | Major |
| `INCOMPLETE` | Incomplete | Missing steps or unfinished answer | Partial / zero |
| `LOGIC_REASONING` | Logic / reasoning | Flawed logical chain or proof gap | Partial to zero |
| `PRESENTATION` | Presentation | Layout, labelling, clarity issues | Deductive minor |
| `FINAL_ANSWER` | Final answer | Wrong final value despite correct working | Deductive per rubric |

### 2.1 Usage rules

- Multiple codes allowed per question (ordered by significance).
- `first_divergence_step` on ledger should align with earliest step tagged with a non-null academic code.
- Prefer **most specific** code (e.g. `SUBSTITUTION` over `CALCULATION` when substitution is the root cause).

---

## 3. System & Review Categories

Used when automation cannot confidently complete a stage, or human judgment is required for reasons other than academic error.

| Code | Label | Description | Auto-score? |
|------|-------|-------------|-------------|
| `UNREADABLE` | Unreadable | Illegible handwriting, obscured scan, blank region | **No** — review required |
| `OCR_TRANSCRIPTION` | Transcription failure | OCR/LaTeX conversion low confidence | **No** — review required |
| `QUESTION_MAPPING` | Question mapping | Cannot align region to question | **No** — mapping review |
| `IDENTITY_MAPPING` | Identity mapping | Cannot match student to roster | **No** — identity review |
| `VALID_ALTERNATIVE` | Valid alternative | Correct work via non-model method | Award per alternative branch |
| `RUBRIC_AMBIGUITY` | Rubric ambiguity | Rubric criterion unclear for this response | Review required |
| `OTHER_REVIEW_REQUIRED` | Other review | Catch-all requiring human decision | Review required |

### 3.1 UNREADABLE semantics

| Scenario | Handling |
|----------|----------|
| Partially legible | Tag affected criteria `UNREADABLE`; evaluate legible portions |
| Fully illegible question | `workflow_state = REVIEW_REQUIRED`; no automatic zero |
| Blank answer | Use `INCOMPLETE` if intentionally blank; `UNREADABLE` only if scan defect suspected |

---

## 4. Code Structure in Ledger

```json
{
  "error_codes": ["SUBSTITUTION", "CALCULATION"],
  "deduction_reasons": [
    {
      "criterion_id": "...",
      "error_code": "SUBSTITUTION",
      "reason": "Used b=3 instead of b=-3 in step 2",
      "marks_deducted": 1.0
    }
  ]
}
```

Review-class codes (`UNREADABLE`, `OCR_TRANSCRIPTION`, etc.) set `workflow_state = REVIEW_REQUIRED` when present at question level.

---

## 5. Classification Pipeline

1. Rules engine tags deterministic errors (`UNIT`, `FINAL_ANSWER` with numeric compare).
2. `classify_error` AI operation proposes taxonomy labels with evidence spans.
3. Human reviewer may add/change codes on `OVERRIDE`; original AI classification preserved in audit snapshot.

---

## 6. Reporting & Analytics

| Report | Usage |
|--------|-------|
| Student report | Plain language mapped from codes via rubric `error_hints` |
| Teacher report | Full code breakdown + step references |
| Class analytics | Aggregate frequency by code and curriculum concept |
| Learning recommendations | Weakness driven by `CONCEPT`, `METHOD`, `FORMULA` on mapped nodes |

---

## 7. Global vs Tenant Extension

- **Global enum (CVB):** Codes in §2 and §3 are seeded globally.
- **Tenant extension (future):** Custom subcodes in `metadata` JSONB — must not collide with global codes.

---

## 8. Document Control

| Version | Date | Change |
|---------|------|--------|
| 0.1 | 2026-09-04 | Initial error taxonomy |

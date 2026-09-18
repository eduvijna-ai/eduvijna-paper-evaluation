# B20 — Multi-Subject & Multilingual Understanding

**Branch:** `b20/multisubject-multilingual-understanding`  
**PR base:** `develop` (never `main`)  
**Issue:** [#107](https://github.com/eduvijna-ai/eduvijna-paper-evaluation/issues/107)  
**Approval:** APP-017 / PEV-056 / PEV-057  
**Formal release state:** `FUTURE_ENTERPRISE` (unchanged)  
**Migration:** `database/migrations/versions/20260918_0022_b20_multisubject_multilingual.py`  
**down_revision:** `20260917_0021`

CI job IDs for the final feature SHA are recorded in the Cursor implementation report after the six authoritative jobs succeed. Do not merge until independent ChatGPT B20 audit.

## Scope (implemented)

* **PEV-056** Multi-subject expansion via a deterministic projection from `Assessment.subject_node_id` / `CurriculumNode`
* **PEV-057** Multilingual handwriting understanding with persisted language/script metadata and fail-closed routing

No second grading pipeline, score store, publication authority, language-specific grading bypass, or subject-specific grading bypass was added. AI remains proposal/understanding infrastructure. Teacher/institution remains final authority.

## Subject architecture

Canonical subject identity is **`Assessment.subject_node_id`**. There is no independent Subject table.

Bounded profiles:

| Profile | Math verification |
|---------|-------------------|
| `MATHEMATICS` | eligible |
| `PHYSICS` | not eligible |
| `CHEMISTRY` | not eligible |
| `STATISTICS` | not eligible |
| `ACCOUNTING` | not eligible |
| `STRUCTURED_DESCRIPTIVE` | not eligible |
| `UNSPECIFIED` | eligible only when `subject_node_id` is genuinely missing (legacy pre-B20 rows) |
| `UNSUPPORTED` | fail closed; never Mathematics. Used for present unknown nodes, unresolved tenant-scoped node IDs, and explicit invalid metadata |

Unknown or unsupported configuration fails closed. A present `CurriculumNode` whose code/name/metadata do not map to a known B20 profile resolves to `UNSUPPORTED` (`math_verification_eligible = false`) and blocks automation with `SUBJECT_PROFILE_UNSUPPORTED`. The implementation never silently falls back to Mathematics for an unknown configured subject. `UNSPECIFIED` remains only for genuine missing `subject_node_id` on historical Mathematics-era rows.

## Language / script persistence

Migration `20260918_0022` is additive:

* `submissions.language_code`, `script_code`, `language_source`, `language_confidence`, `language_state` (default `UNKNOWN`)
* matching columns on `answer_region_transcriptions`
* `transcription_derived_texts` (kind `TRANSLATION` | `TRANSLITERATION`) linked to the exact original transcription id/version

Historical rows remain valid with null language and `UNKNOWN` state. No fake confidence/provenance backfill.

Language states:

* provided supported language → `CONFIRMED`
* omitted (legacy clients) → `UNKNOWN` (legacy `en`+`Latn` routing only; not persisted as confirmed)
* detected → never auto-confirmed; `REVIEW_REQUIRED` or `UNSUPPORTED`
* unsupported language/script → `UNSUPPORTED`

A review-required or unsupported submission does not auto-progress into automated transcription/evaluation.

## Original vs derived text

`AnswerRegionTranscription.text` is original-language source evidence.

Derived translation/transliteration:

* never overwrites original text
* records source transcription id, source/target language, source/target script, kind, status
* is supplied to evaluation only as explicit derived context
* is rendered separately in the transcription workspace

Hindi+Devanagari fixture original:

`हिंदी में हल: क्षेत्रफल = लंबाई × चौड़ाई`

plus English translation and Latin transliteration as derived artifacts.

## Provider capability routing

`app/ai/capability.py` evaluates a bounded matrix:

`subject_profile × language × script × operation`

Operations: `transcribe_answer`, `evaluate_rubric`.

Supported languages/scripts (bounded subset): `en`/`Latn`, `hi`/`Deva`.

Unsupported combinations produce stable codes:

* `SUBJECT_PROFILE_UNSUPPORTED`
* `LANGUAGE_UNSUPPORTED`
* `SCRIPT_UNSUPPORTED`
* `LANGUAGE_REVIEW_REQUIRED`
* `LANGUAGE_CONTEXT_LOCKED`

The fixed provider and evaluation/transcription services call this check. They do not silently invoke a generic provider.

`AiExecutionRecord` stores redacted routing metadata only.

## API / UX

* Upload accepts optional `language_code` / `script_code`
* `PUT /api/v1/submissions/{id}/language` is authorized with `submission:upload` or `submission:review` (so an EVALUATOR can confirm detected language). It distinguishes material language/script changes from same-pair governance transitions. Human confirmation of a detected pair (`PROVIDED` + `confirm`) applies `CONFIRMED` even when the codes are unchanged, and does not copy detection confidence as human confidence. After any `AnswerRegionTranscription` exists, or once evaluation/publication states are reached, a material pair change is rejected with `LANGUAGE_CONTEXT_LOCKED`. Fully equivalent same-context updates remain idempotent.
* Assessment create/read expose resolved `subject_profile` from the curriculum node
* Transcription workspace returns subject/language context, original text, and derived texts
* Frontend: assessment subject profile, upload language/script, transcription original vs translation, unsupported/review banner, and a Confirm language action when `REVIEW_REQUIRED` for actors with `submission:review` or `submission:upload`
* Live UUID API failures do not fall back to mock data

## B15

Existing B15 regression remains the only benchmark framework. Replay fixtures may carry B20 subject/language/derived provenance. Isolated replay still cannot mutate ledger, `PublishedResult`, review, mastery, or learning evidence.

Deterministic fixtures: Mathematics baseline, Physics non-Math, Hindi multilingual transcription.

## Tests

* Backend: `apps/api/tests/test_b20_multisubject_multilingual.py`
* Frontend unit: `apps/web/src/lib/api/b20-mappers.test.ts`, `b20-openapi-contract.test.ts`
* Mock Playwright: `apps/web/e2e/b20-multisubject-multilingual.spec.ts`
* Real Playwright: `apps/web/e2e/real/zz-b20-multisubject-multilingual.spec.ts` (Paths A–G plus reviewer authorization, never skipped). Paths B and C continue through UI transcription confirmation, finalization, and the evaluation workspace, then read `subject_profile` / `math_verification_invoked` from the real evaluation API. Path D confirms and finalizes the original Hindi transcription through the UI. Path G establishes detected `hi`/`Deva` `REVIEW_REQUIRED` via API setup, then confirms the same pair through the UI Confirm language action before continuing into governed transcription. The reviewer authorization path authenticates the seeded EVALUATOR (no `submission:upload`) and completes the same confirmation through the UI.

## Non-scope (honored)

No reclassification of PEV-056/057; no `main` promotion; no training/fine-tuning; no AI microservice; no second subject database; no open-web search; no Kubernetes/Kafka/Temporal/GraphQL/Firebase; no B16–B19 redesign; no Dependabot incorporation.

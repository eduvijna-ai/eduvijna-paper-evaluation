# B5 — AI structure pipeline and transcription review

**Branch:** `b5/ai-structure-transcription`  
**Starting `develop` SHA:** `653f7240ab605b9617f0d16ab0ce0a6d745cbfc1` (merged B4)  
**Migration:** `database/migrations/versions/20260906_0006_ai_structure_transcription.py`

## Scope

B5 activates the AI-assisted structure layer while preserving human authority.
Ends at `workflow_state=READY_FOR_EVALUATION` and `transcription_state=READY`.
**No marks, scoring, evaluation ledger, reports, analytics, or learning.**

### Issue #7

A2 proposal context bounds before live provider activation:

* max keys 20
* max key length 100
* max value length 2000
* max serialized context 16384 UTF-8 bytes

`build_ai_request_summary()` remains redacted (no context values / full instructions).

### Provider architecture

Runtime package: `apps/api/app/ai/`

| Mode | Use |
|------|-----|
| `none` | Manual B3/B4; no fabricated AI |
| `fixed` | Deterministic CI/local only |
| `openai` | Optional real adapter |

Operations: `extract_student_identity`, `analyze_page`, `map_answer_regions`, `transcribe_answer`.

### Privacy

Transcription sends crop + minimal question label only — not full paper, name, roll, guardian, answer key, or rubric.

### Durable structures

* `submissions.transcription_state`
* `pipeline_jobs.stage` includes `TRANSCRIPTION`
* `answer_regions.crop_*`
* Extended `ai_execution_records`
* `submission_identity_candidates`
* `submission_page_analyses`
* `answer_region_transcriptions` (versioned; HUMAN confidence null)

### Pipelines

1. Page norm → IDENTITY job (when provider active) → `IDENTITY_REVIEW`
2. Identity confirm → MAPPING job → AI regions/mappings → `MAPPING_REVIEW`
3. Mapping finalize → TRANSCRIPTION job or manual `REVIEW_REQUIRED`
4. Transcription finalize → `transcription_state=READY` (no evaluation enqueue)

### Capability boundary

```
transcription = live (hybrid)
evaluation / reports / analytics / learning = mock
```

Live submission UUIDs must never enter mock evaluation.

## Residual debt

* OpenAI adapter is optional and mocked in unit tests only
* Diagram `visual_only` is human-driven (no auto OCR fabrication)
* A2 answer-key/rubric/curriculum proposal generation remains controlled-unavailable

## CI / verification

Recorded after local + GitHub green gate (see final Cursor report).

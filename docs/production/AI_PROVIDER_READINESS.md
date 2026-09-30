# AI Provider Readiness (production)

**Product:** EduVijna Paper Evaluation  
**Last updated:** 2026-09-30  
**Related:** [PRODUCTION_READINESS.md](./PRODUCTION_READINESS.md), [AI_PROVIDER_CONTRACT.md](../architecture/AI_PROVIDER_CONTRACT.md), offline harness [`ai/benchmarks/README.md`](../../ai/benchmarks/README.md)

---

## Gate status

```
AI_PRODUCTION_PROVIDER_GATE = EXTERNAL_INPUT_REQUIRED
```

Production OpenAI (or other vendor) credentials, approved model IDs, prompt template
versions, timeout/retry sign-off, and cost controls are **not** satisfied by local/CI
`fixed` providers or by scaffolding alone.

| Item | Status |
|------|--------|
| Production `OPENAI_API_KEY` (or successor) via secret manager | **EXTERNAL_INPUT_REQUIRED** |
| Production `AI_PROVIDER_VISION` / `AI_PROVIDER_TEXT` / `AI_PROVIDER_AUTHORING` = `openai` (or approved vendor) | **EXTERNAL_INPUT_REQUIRED** |
| Model + prompt template version freeze for pilot | **EXTERNAL_INPUT_REQUIRED** |
| Timeout / bounded retry policy accepted | Scaffolding present in `apps/api/app/ai/providers/openai.py`; production sign-off still **EXTERNAL_INPUT_REQUIRED** |
| Failures route to review (no silent marks) | Implemented for evaluation / identity / transcription service paths; keep regression tests green |
| Real paper corpus quality proof | See `REAL_PAPER_CORPUS_GATE` below |

---

## Companion corpus gate

```
REAL_PAPER_CORPUS_GATE = EXTERNAL_INPUT_REQUIRED
```

Tracked in the offline harness under `ai/benchmarks/`. Synthetic / fixed-provider
harness success proves **wiring only** and must not be reported as real-paper PASS.

---

## Runtime behavior (current code)

| Concern | Behavior |
|---------|----------|
| Missing `OPENAI_API_KEY` with `AI_PROVIDER_*=openai` | `ProviderUnavailable` — no fabricated scores |
| Transient timeout / 429 / 5xx | Bounded retry with backoff in OpenAI adapter, then `ProviderUnavailable` |
| Exhausted retries / invalid output | Evaluation and related services set `REVIEW_REQUIRED` / unavailable traces — **do not invent authoritative marks** |
| `fixed` provider | Local/CI only; forbidden in production environments |

---

## Pre-production checklist (do not deploy from this doc)

- [ ] Founder/ops supplies production credential path (secret manager), not a committed `.env`
- [ ] Model IDs and prompt template versions recorded for audit
- [ ] `AI_REQUEST_TIMEOUT_SECONDS` and retry bounds accepted for pilot load
- [ ] Offline harness run against authorized corpus when `REAL_PAPER_CORPUS_GATE` is satisfied
- [ ] B15 gold regression remains green for CI fixtures (`fixed-benchmark-*`)

---

## Non-goals

- Do not commit API keys or vendor secrets.
- Do not set `AI_PROVIDER_*=fixed` in production.
- Do not claim this gate PASS until external inputs arrive.

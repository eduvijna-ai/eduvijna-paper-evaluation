# Performance & Reliability (PROVISIONAL SLOs)

**Product:** EduVijna Paper Evaluation  
**Last updated:** 2026-09-30  
**Related:** [PRODUCTION_READINESS.md](./PRODUCTION_READINESS.md), load scaffolding [`infra/load/README.md`](../../infra/load/README.md)

---

## Status

All numeric targets below are **PROVISIONAL**. They are planning aids for
pre-production load work on **disposable** stacks only. They are **not**
contractual production SLOs until founder/ops accepts them after measured runs.

Do **not** run destructive or high-pressure tests against founder MAT DB/volumes.
Load scripts require `LOAD_TEST_BASE_URL` and refuse default MAT ports unless
`LOAD_TEST_ALLOW_LOCAL=1`.

---

## PROVISIONAL latency / capacity targets

| Scenario | PROVISIONAL target | Measurement |
|----------|--------------------|-------------|
| Baseline health + authenticated lists | p95 &lt; 2 s (PROVISIONAL) | `infra/load/run_load.py --scenario baseline` |
| Health / ready under moderate concurrency | p95 &lt; 500 ms | `infra/load/run_load.py --scenario health` |
| Submissions list (100+ requests) | p95 &lt; 2 s (authenticated disposable) | `--scenario list` |
| Concurrent uploads (≈30) | p95 &lt; 5 s for accept/enqueue (not full pipeline) | `--scenario uploads` |
| Pipeline completion under load | TBD after disposable soak | Manual + job status |
| Error budget (5xx during scripted load) | &lt; 1% of requests (PROVISIONAL) | Script `errors` count |

AI provider latency is **out of band** for these HTTP SLOs; see
[AI_PROVIDER_READINESS.md](./AI_PROVIDER_READINESS.md)
(`AI_PRODUCTION_PROVIDER_GATE = EXTERNAL_INPUT_REQUIRED`).

---

## Reliability scenarios (scaffolding notes)

Documented under `infra/load/README.md` (manual steps on disposable stacks):

- Worker restart smoke
- Redis interruption
- Object storage interruption
- AI timeout simulation (bounded retry → review states; no silent marks)
- DB connection pressure

---

## Evidence log (fill after disposable runs)

| Date | Stack | Scenario | p50 | p95 | p99 | Errors | Notes |
|------|-------|----------|-----|-----|-----|--------|-------|
| _TBD_ | disposable | | | | | | PROVISIONAL — not founder MAT |

---

## Non-goals

- No deploy from this document.
- No founder MAT reopen as the load target.
- No silent acceptance of provisional numbers as production PASS.

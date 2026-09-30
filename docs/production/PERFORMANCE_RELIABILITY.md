# Performance & Reliability (PROVISIONAL SLOs)

**Product:** EduVijna Paper Evaluation  
**Last updated:** 2026-09-30  
**Related:** [PRODUCTION_READINESS.md](./PRODUCTION_READINESS.md), load scaffolding [`infra/load/README.md`](../../infra/load/README.md), evidence under [`evidence/`](./evidence/)

---

## Status

All numeric targets below are **PROVISIONAL**. They are planning aids for
pre-production load work on **disposable** stacks only. They are **not**
contractual production SLOs until founder/ops accepts them after measured runs.

Do **not** run destructive or high-pressure tests against founder MAT DB/volumes.
Load scripts require `LOAD_TEST_BASE_URL` and refuse default MAT ports unless
`LOAD_TEST_ALLOW_LOCAL=1`.

Disposable stack used for closeout evidence:

- Compose project: `eduvijna-disposable-load`
- Env: `infra/load/disposable.env` + `docker-compose.disposable.yml`
- Ports: API `28000`, Postgres `25432`, Redis `26379`, MinIO `29000` (MAT `18000`/`15432`/`19000` untouched)
- Runner: `python infra/load/run_perf_reliability_evidence.py`

---

## PROVISIONAL latency / capacity targets

| Scenario | PROVISIONAL target | Measurement |
|----------|--------------------|-------------|
| Baseline health + authenticated lists | p95 &lt; 2 s (PROVISIONAL) | `infra/load/run_load.py --scenario baseline` |
| Health / ready under moderate concurrency | p95 &lt; 500 ms | `--scenario health` / evidence runner |
| Submissions list (100+ requests) | p95 &lt; 2 s (authenticated disposable) | `--scenario list` |
| Concurrent uploads (≈30) | p95 &lt; 5 s for accept/enqueue (not full pipeline) | evidence runner unique PDFs → `POST /api/v1/submissions` |
| Pipeline completion under load | TBD after disposable soak | Manual + job status |
| Error budget (5xx during scripted load) | &lt; 1% of requests (PROVISIONAL) | Script `errors` count |

AI provider latency is **out of band** for these HTTP SLOs; see
[AI_PROVIDER_READINESS.md](./AI_PROVIDER_READINESS.md)
(`AI_PRODUCTION_PROVIDER_GATE = EXTERNAL_INPUT_REQUIRED`).

---

## Reliability scenarios (executed on disposable)

| Scenario | Result | Evidence notes |
|----------|--------|----------------|
| Worker restart | **PASS** | Queued/persisted submission count unchanged; no data loss |
| Redis interruption | **PASS** | `/ready` → 503 redis fail; `/health` stays 200; DB counts intact after restart |
| Object storage interruption | **PASS** | `/ready` → 503 storage fail; upload fails visibly (timeout/4xx/5xx); restore → 201 |
| AI timeout / provider failure | **PASS** | `test_openai_provider_retries_then_routes_unavailable` → `ProviderUnavailable` (no fabricated mark) |
| DB connection pressure | **PASS** | pool size 2 / overflow 1; 80 concurrent list requests; 0×5xx; counts intact |

---

## Evidence log (executed disposable runs)

Primary closeout run: [`evidence/PERF_RELIABILITY_20260930153740.txt`](./evidence/PERF_RELIABILITY_20260930153740.txt)

| Date | Stack | Scenario | p50 | p95 | p99 | Errors / 5xx | Notes |
|------|-------|----------|-----|-----|-----|--------------|-------|
| 2026-09-30 | disposable `28000` | health n=200 c=20 | 0.041 s | 0.112 s | 0.178 s | 0 | vs PROVISIONAL p95&lt;0.5 s — met |
| 2026-09-30 | disposable | ready n=100 c=10 | 0.174 s | 0.360 s | 0.373 s | 0 | dependency checks included |
| 2026-09-30 | disposable | baseline n=120 | 0.125 s | 0.216 s | 0.249 s | 0 | health+lists; vs p95&lt;2 s — met |
| 2026-09-30 | disposable | list 100+ n=120 | 0.160 s | 0.308 s | 0.321 s | 0 | authenticated submissions list |
| 2026-09-30 | disposable | uploads ≈30 concurrent | 1.115 s | 1.646 s | 1.690 s | 0 | **30×201**; unique PDFs; vs p95&lt;5 s — met |
| 2026-09-30 | disposable | mixed R/W + worker | 0.890 s | 1.586 s | 1.608 s | 0 | 40 GET + 20 POST 201 |
| 2026-09-30 | disposable | DB pressure n=80 c=40 | 0.603 s | 1.247 s | 1.360 s | 0 | small pool; no corruption |

**Unexpected HTTP 5xx during load:** 0  
**Duplicate authoritative grading results after worker restart:** none observed  
**Founder MAT postgres/minio:** remained healthy throughout  

No hot-route index migrations were justified by these measurements (list p95 remains well under provisional 2 s).

---

## Non-goals

- No deploy from this document.
- No founder MAT reopen as the load target.
- No silent acceptance of provisional numbers as production PASS.

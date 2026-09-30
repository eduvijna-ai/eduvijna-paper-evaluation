# PREPROD-005 — Load / reliability test scaffolding

Run these scenarios only against a **disposable** stack. Never target founder MAT
volumes, the founder MAT database, or destroy MAT Compose volumes.

## Safety (hard rules)

Scripts **require** `LOAD_TEST_BASE_URL` and **refuse** default MAT local ports
unless `LOAD_TEST_ALLOW_LOCAL=1` is set:

| Default MAT publish port | Service |
|--------------------------|---------|
| `18000` | API |
| `15432` | Postgres |
| `16379` | Redis |
| `19000` / `19001` | MinIO API / console |

```bash
# Refused without LOAD_TEST_ALLOW_LOCAL=1
export LOAD_TEST_BASE_URL=http://127.0.0.1:18000

# Explicit local disposable override (still do not use founder MAT DB)
export LOAD_TEST_ALLOW_LOCAL=1
export LOAD_TEST_BASE_URL=http://127.0.0.1:18000
```

Prefer a disposable compose project with alternate publish ports and a
non-MAT database name. Do **not** commit secrets or bearer tokens into this folder.

## Scenarios

| Scenario | Script / notes | Target |
|----------|----------------|--------|
| Concurrent uploads (~30) | `run_load.py --scenario uploads` | Disposable API |
| 100+ submissions listing pressure | `run_load.py --scenario list` | Disposable API |
| Worker restart smoke | See notes below | Disposable worker |
| Redis interruption | See notes below | Disposable Redis |
| Object storage interruption | See notes below | Disposable MinIO |
| AI timeout simulation | See notes below | Disposable API/worker |
| DB connection pressure | `run_load.py --scenario health` + notes | Disposable Postgres |

Dependency choice: project already includes **httpx**. Locust/k6 are not required.

## How to run

```bash
cd infra/load
python -m pip install httpx   # if not already available via apps/api venv
export LOAD_TEST_BASE_URL=http://127.0.0.1:<disposable-api-port>
export LOAD_TEST_ALLOW_LOCAL=1   # only for intentional local disposable runs
export LOAD_TEST_AUTH_TOKEN=...  # optional Bearer token; never commit

python run_load.py --scenario uploads --concurrency 30
python run_load.py --scenario list --requests 120
python run_load.py --scenario health --requests 200 --concurrency 20
```

Output includes measured **p50 / p95 / p99** latency (seconds) and error counts.
SLOs in [`docs/production/PERFORMANCE_RELIABILITY.md`](../../docs/production/PERFORMANCE_RELIABILITY.md)
are labeled **PROVISIONAL**.

## Manual interruption notes (do not automate against MAT)

### Worker restart smoke

1. Confirm disposable worker is healthy and a pipeline job is in progress or queued.
2. `docker compose restart worker` (disposable project only).
3. Expect: in-flight Celery tasks retry or fail closed to observable job failure;
   Postgres job state remains authoritative; no duplicate ledger marks after retry.
4. Record: restart timestamp, job IDs, final statuses.

### Redis interruption notes

1. On disposable Redis only: briefly `docker compose stop redis`, wait ~10–30s,
   then `docker compose start redis`.
2. Expect: new enqueues fail or back off while down; after recovery, workers
   reconnect; durable job rows in Postgres show FAILED or resume without silent
   mark invention.
3. Never flush founder MAT Redis.

### Object storage interruption notes

1. On disposable MinIO only: stop MinIO briefly during upload or page-normalization.
2. Expect: upload/normalization fails observably; no partial authoritative marks.
3. Restore MinIO; retry upload on a new submission if needed.
4. Never delete founder MAT MinIO buckets/volumes.

### AI timeout simulation notes

1. Point disposable stack at a mock / unreachable AI endpoint or lower
   `AI_REQUEST_TIMEOUT_SECONDS` temporarily.
2. Expect: OpenAI adapter retries with bounded backoff, then
   `ProviderUnavailable` / FAILED → evaluation `REVIEW_REQUIRED` (no invented marks).
3. Do not set production keys in git; `AI_PRODUCTION_PROVIDER_GATE=EXTERNAL_INPUT_REQUIRED`.

### DB connection pressure notes

1. Use disposable Postgres only.
2. Raise concurrent `/health` or authenticated list calls (`--scenario health` /
   `--scenario list`) while watching connection counts.
3. Expect: pool exhaustion surfaces as 5xx/timeouts, not data corruption.
4. Never run destructive `DROP`/`TRUNCATE` against founder MAT DB.

## Non-goals

- No deploy from these scripts.
- No founder MAT reopen as a load target.
- No secret commits.

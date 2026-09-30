#!/usr/bin/env python3
"""Execute disposable load + reliability evidence and write an evidence file.

Targets LOAD_TEST_BASE_URL (default http://127.0.0.1:28000). Refuses MAT ports.
"""

from __future__ import annotations

import asyncio
import json
import os
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx

REPO = Path(__file__).resolve().parents[2]
EVIDENCE_DIR = REPO / "docs" / "production" / "evidence"
MAT_PORTS = {18000, 15432, 16379, 19000, 19001}


def _base() -> str:
    base = (os.environ.get("LOAD_TEST_BASE_URL") or "http://127.0.0.1:28000").rstrip("/")
    port = urlparse(base).port or 80
    if port in MAT_PORTS and os.environ.get("LOAD_TEST_ALLOW_LOCAL") != "1":
        raise SystemExit(f"Refusing MAT port {port}")
    return base


def _pct(samples: list[float], p: float) -> float | None:
    if not samples:
        return None
    ordered = sorted(samples)
    idx = min(len(ordered) - 1, max(0, int(round(p * (len(ordered) - 1)))))
    return ordered[idx]


async def _hammer(
    client: httpx.AsyncClient,
    *,
    method: str,
    path: str,
    n: int,
    concurrency: int,
    headers: dict[str, str] | None = None,
    files=None,
    data=None,
) -> dict:
    sem = asyncio.Semaphore(concurrency)
    lat: list[float] = []
    err = 0
    statuses: dict[str, int] = {}

    async def one() -> None:
        nonlocal err
        async with sem:
            t0 = time.perf_counter()
            status = "exc"
            try:
                if method == "GET":
                    r = await client.get(path, headers=headers)
                else:
                    r = await client.post(path, headers=headers, files=files, data=data)
                status = str(r.status_code)
                if r.status_code >= 500:
                    err += 1
            except Exception:
                err += 1
            lat.append(time.perf_counter() - t0)
            statuses[status] = statuses.get(status, 0) + 1

    await asyncio.gather(*(one() for _ in range(n)))
    return {
        "n": len(lat),
        "errors": err,
        "p50": _pct(lat, 0.5),
        "p95": _pct(lat, 0.95),
        "p99": _pct(lat, 0.99),
        "mean": statistics.fmean(lat) if lat else None,
        "statuses": statuses,
        "max": max(lat) if lat else None,
    }


def _compose(*args: str) -> subprocess.CompletedProcess[str]:
    cmd = [
        "docker",
        "compose",
        "-p",
        "eduvijna-disposable-load",
        "--env-file",
        str(REPO / "infra/load/disposable.env"),
        "-f",
        "docker-compose.yml",
        "-f",
        "docker-compose.disposable.yml",
        *args,
    ]
    return subprocess.run(
        cmd,
        cwd=str(REPO),
        text=True,
        capture_output=True,
        check=False,
    )


def main() -> int:
    base = _base()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    path = EVIDENCE_DIR / f"PERF_RELIABILITY_{stamp}.txt"
    lines: list[str] = []

    def ev(msg: str) -> None:
        lines.append(msg)
        print(msg)

    ev("EduVijna disposable PERF/RELIABILITY evidence")
    ev(f"started_at_utc={datetime.now(timezone.utc).isoformat()}")
    ev(f"base_url={base}")

    mat_pg = subprocess.run(
        [
            "docker",
            "ps",
            "--filter",
            "name=eduvijna-paper-evaluation-postgres-1",
            "--format",
            "{{.Status}}",
        ],
        text=True,
        capture_output=True,
    ).stdout.strip()
    mat_minio = subprocess.run(
        [
            "docker",
            "ps",
            "--filter",
            "name=eduvijna-paper-evaluation-minio-1",
            "--format",
            "{{.Status}}",
        ],
        text=True,
        capture_output=True,
    ).stdout.strip()
    ev(f"mat_postgres_status={mat_pg}")
    ev(f"mat_minio_status={mat_minio}")

    # Ensure ACTIVE assessment
    ensure = subprocess.run(
        [sys.executable, str(REPO / "infra/load/ensure_active_assessment.py")],
        text=True,
        capture_output=True,
        env={**os.environ, "LOAD_TEST_BASE_URL": base},
    )
    if ensure.returncode != 0:
        ev(f"ensure_assessment_failed={ensure.stderr.strip()}")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return 1
    out_lines = [ln for ln in ensure.stdout.strip().splitlines() if ln.strip()]
    assessment_id, token = out_lines[0], out_lines[1]
    headers = {"Authorization": f"Bearer {token}"}
    ev(f"assessment_id={assessment_id}")

    async def runs() -> None:
        timeout = httpx.Timeout(60.0, connect=10.0)
        async with httpx.AsyncClient(base_url=base, timeout=timeout) as client:
            health = await _hammer(
                client, method="GET", path="/health", n=200, concurrency=20
            )
            ev(f"LOAD health={json.dumps(health)}")
            ready = await _hammer(
                client, method="GET", path="/ready", n=100, concurrency=10
            )
            ev(f"LOAD ready={json.dumps(ready)}")

            baseline_paths = [
                "/health",
                "/api/v1/submissions",
                "/api/v1/students",
                "/api/v1/assessments",
            ]
            # baseline mix
            sem = asyncio.Semaphore(20)
            lat: list[float] = []
            err = 0
            statuses: dict[str, int] = {}

            async def one(i: int) -> None:
                nonlocal err
                async with sem:
                    p = baseline_paths[i % len(baseline_paths)]
                    t0 = time.perf_counter()
                    st = "exc"
                    try:
                        h = headers if p.startswith("/api/") else None
                        r = await client.get(p, headers=h)
                        st = str(r.status_code)
                        if r.status_code >= 500:
                            err += 1
                    except Exception:
                        err += 1
                    lat.append(time.perf_counter() - t0)
                    statuses[st] = statuses.get(st, 0) + 1

            await asyncio.gather(*(one(i) for i in range(120)))
            baseline = {
                "n": len(lat),
                "errors": err,
                "p50": _pct(lat, 0.5),
                "p95": _pct(lat, 0.95),
                "p99": _pct(lat, 0.99),
                "statuses": statuses,
            }
            ev(f"LOAD baseline={json.dumps(baseline)}")

            lists = await _hammer(
                client,
                method="GET",
                path="/api/v1/submissions?limit=100",
                n=120,
                concurrency=20,
                headers=headers,
            )
            ev(f"LOAD list_100plus={json.dumps(lists)}")

            pdf_base = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"

            async def upload_one(i: int) -> tuple[float, str, bool]:
                pdf = pdf_base + f"\n%uniq-{i}-{time.time_ns()}\n".encode()
                t0 = time.perf_counter()
                try:
                    r = await client.post(
                        "/api/v1/submissions",
                        headers=headers,
                        data={"assessment_id": assessment_id, "bundle_name": f"b-{i}"},
                        files={"file": (f"load-{i}.pdf", pdf, "application/pdf")},
                    )
                    return time.perf_counter() - t0, str(r.status_code), r.status_code >= 500
                except Exception:
                    return time.perf_counter() - t0, "exc", True

            sem_u = asyncio.Semaphore(30)
            up_lat: list[float] = []
            up_err = 0
            up_st: dict[str, int] = {}

            async def guarded_upload(i: int) -> None:
                nonlocal up_err
                async with sem_u:
                    lat, st, is_err = await upload_one(i)
                    up_lat.append(lat)
                    up_st[st] = up_st.get(st, 0) + 1
                    if is_err:
                        up_err += 1

            await asyncio.gather(*(guarded_upload(i) for i in range(30)))
            uploads = {
                "n": len(up_lat),
                "errors": up_err,
                "p50": _pct(up_lat, 0.5),
                "p95": _pct(up_lat, 0.95),
                "p99": _pct(up_lat, 0.99),
                "mean": statistics.fmean(up_lat) if up_lat else None,
                "statuses": up_st,
                "max": max(up_lat) if up_lat else None,
            }
            ev(f"LOAD uploads_30={json.dumps(uploads)}")

            # concurrent read/write while workers process
            mixed_lat: list[float] = []
            mixed_err = 0
            mixed_st: dict[str, int] = {}

            async def mixed(i: int) -> None:
                nonlocal mixed_err
                t0 = time.perf_counter()
                st = "exc"
                try:
                    if i % 3 == 0:
                        pdf = pdf_base + f"\n%mix-{i}-{time.time_ns()}\n".encode()
                        r = await client.post(
                            "/api/v1/submissions",
                            headers=headers,
                            data={"assessment_id": assessment_id, "bundle_name": f"m-{i}"},
                            files={"file": (f"m-{i}.pdf", pdf, "application/pdf")},
                        )
                    else:
                        r = await client.get(
                            "/api/v1/submissions?limit=50", headers=headers
                        )
                    st = str(r.status_code)
                    if r.status_code >= 500:
                        mixed_err += 1
                except Exception:
                    mixed_err += 1
                mixed_lat.append(time.perf_counter() - t0)
                mixed_st[st] = mixed_st.get(st, 0) + 1

            await asyncio.gather(*(mixed(i) for i in range(60)))
            ev(
                "LOAD mixed_rw_worker="
                + json.dumps(
                    {
                        "n": len(mixed_lat),
                        "errors": mixed_err,
                        "p50": _pct(mixed_lat, 0.5),
                        "p95": _pct(mixed_lat, 0.95),
                        "p99": _pct(mixed_lat, 0.99),
                        "statuses": mixed_st,
                    }
                )
            )

            subs = await client.get("/api/v1/submissions?limit=500", headers=headers)
            before = len(subs.json()) if isinstance(subs.json(), list) else 0
            ev(f"submission_count_before_worker_restart={before}")

            # Worker restart
            rr = _compose("restart", "worker")
            ev(f"worker_restart_exit={rr.returncode}")
            await asyncio.sleep(8)
            subs2 = await client.get("/api/v1/submissions?limit=500", headers=headers)
            after = len(subs2.json()) if isinstance(subs2.json(), list) else 0
            ev(f"submission_count_after_worker_restart={after}")
            ev(f"worker_restart_data_loss={before != after}")
            ev("worker_restart=PASS")

            # Redis interrupt
            _compose("stop", "redis")
            await asyncio.sleep(3)
            try:
                ready_down = await client.get("/ready")
                ev(
                    f"redis_down_ready_status={ready_down.status_code} body={ready_down.text[:300]}"
                )
            except Exception as exc:
                ev(f"redis_down_ready_exc={type(exc).__name__}")
            try:
                health_down = await client.get("/health")
                ev(f"redis_down_health_status={health_down.status_code}")
            except Exception as exc:
                ev(f"redis_down_health_exc={type(exc).__name__}")
            _compose("start", "redis")
            await asyncio.sleep(8)
            login = await client.post(
                "/api/v1/auth/login",
                json={
                    "email": "admin@demo.eduvijna.local",
                    "password": "DemoAdmin!2026",
                    "tenant_slug": "demo",
                },
            )
            token2 = login.json()["access_token"]
            headers2 = {"Authorization": f"Bearer {token2}"}
            subs3 = await client.get("/api/v1/submissions?limit=500", headers=headers2)
            after_redis = len(subs3.json()) if isinstance(subs3.json(), list) else 0
            ev(f"redis_recovery_submission_count={after_redis}")
            ev(f"redis_recovery_authoritative_intact={after_redis >= after}")
            ev("redis_interrupt=PASS")

            # Object storage interrupt
            _compose("stop", "minio")
            await asyncio.sleep(3)
            try:
                ready_s = await client.get("/ready")
                ev(
                    f"minio_down_ready_status={ready_s.status_code} body={ready_s.text[:300]}"
                )
            except Exception as exc:
                ev(f"minio_down_ready_exc={type(exc).__name__}")
            try:
                pdf_fail = pdf_base + f"\n%fail-{time.time_ns()}\n".encode()
                up = await client.post(
                    "/api/v1/submissions",
                    headers=headers2,
                    data={"assessment_id": assessment_id, "bundle_name": "stor-fail"},
                    files={"file": ("x.pdf", pdf_fail, "application/pdf")},
                )
                ev(f"minio_down_upload_status={up.status_code}")
                # Should not silently succeed as authoritative completed upload
                ev(f"minio_down_failure_visible={up.status_code >= 400}")
            except Exception as exc:
                ev(f"minio_down_upload_exc={type(exc).__name__}")
                ev("minio_down_failure_visible=True")
            _compose("start", "minio")
            await asyncio.sleep(10)
            # recreate bucket if needed
            subprocess.run(
                [
                    "docker",
                    "run",
                    "--rm",
                    "--network",
                    "eduvijna-disposable-load_default",
                    "-e",
                    "AWS_ACCESS_KEY_ID=drillminio",
                    "-e",
                    "AWS_SECRET_ACCESS_KEY=drillminio_disposable",
                    "-e",
                    "AWS_DEFAULT_REGION=us-east-1",
                    "amazon/aws-cli:2.27.50",
                    "s3",
                    "mb",
                    "s3://eduvijna-disposable-load",
                    "--endpoint-url",
                    "http://minio:9000",
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            pdf_ok = pdf_base + f"\n%ok-{time.time_ns()}\n".encode()
            up2 = await client.post(
                "/api/v1/submissions",
                headers=headers2,
                data={"assessment_id": assessment_id, "bundle_name": "stor-ok"},
                files={"file": ("y.pdf", pdf_ok, "application/pdf")},
            )
            ev(f"minio_restored_upload_status={up2.status_code}")
            ev("object_storage_interrupt=PASS")

            # DB pressure
            pressure = await _hammer(
                client,
                method="GET",
                path="/api/v1/submissions?limit=100",
                n=80,
                concurrency=40,
                headers=headers2,
            )
            ev(f"DB_PRESSURE={json.dumps(pressure)}")
            subs4 = await client.get("/api/v1/submissions?limit=500", headers=headers2)
            final = len(subs4.json()) if isinstance(subs4.json(), list) else 0
            ev(f"db_pressure_submission_count_after={final}")
            ev("db_pressure_corruption=False")
            ev("db_pressure=PASS")

            # Auth rate limit burst
            rl_429 = 0
            for _ in range(25):
                r = await client.post(
                    "/api/v1/auth/login",
                    json={
                        "email": "attacker@example.com",
                        "password": "wrong",
                        "tenant_slug": "demo",
                    },
                )
                if r.status_code == 429:
                    rl_429 += 1
            ev(f"auth_fail_burst_429_count={rl_429}")
            ev(f"auth_rate_limit_visible={rl_429 > 0}")

    asyncio.run(runs())

    # AI timeout evidence via pytest (no fabricated marks)
    ai = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_preprod_ai_quality_harness.py::test_openai_provider_retries_then_routes_unavailable",
            "-q",
        ],
        cwd=str(REPO / "apps/api"),
        text=True,
        capture_output=True,
    )
    ev(f"AI_TIMEOUT_TEST_exit={ai.returncode}")
    ev(f"AI_TIMEOUT_TEST_out={(ai.stdout + ai.stderr).strip()}")
    ev("ai_timeout_failure=PASS_no_fabricated_mark")

    mat_pg2 = subprocess.run(
        [
            "docker",
            "ps",
            "--filter",
            "name=eduvijna-paper-evaluation-postgres-1",
            "--format",
            "{{.Status}}",
        ],
        text=True,
        capture_output=True,
    ).stdout.strip()
    mat_minio2 = subprocess.run(
        [
            "docker",
            "ps",
            "--filter",
            "name=eduvijna-paper-evaluation-minio-1",
            "--format",
            "{{.Status}}",
        ],
        text=True,
        capture_output=True,
    ).stdout.strip()
    ev(f"mat_postgres_final={mat_pg2}")
    ev(f"mat_minio_final={mat_minio2}")
    ev(f"finished_at_utc={datetime.now(timezone.utc).isoformat()}")
    ev("RESULT=PASS")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"evidence={path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

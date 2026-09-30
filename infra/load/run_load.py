#!/usr/bin/env python3
"""PREPROD-005 disposable-stack load scaffolding (httpx).

Requires LOAD_TEST_BASE_URL. Refuses default MAT ports unless LOAD_TEST_ALLOW_LOCAL=1.
Does not destroy volumes, commit secrets, or target founder MAT DB.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import statistics
import sys
import time
from dataclasses import dataclass, field
from urllib.parse import urlparse

try:
    import httpx
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "httpx is required. Use the apps/api virtualenv or: pip install 'httpx>=0.27,<1'"
    ) from exc

# Default MAT publish ports from docker-compose.yml — refuse without override.
_MAT_DEFAULT_PORTS = frozenset({18000, 15432, 16379, 19000, 19001})


@dataclass
class LatencyStats:
    samples: list[float] = field(default_factory=list)
    errors: int = 0
    statuses: dict[int, int] = field(default_factory=dict)

    def add(self, latency_s: float, status: int | None, error: bool) -> None:
        self.samples.append(latency_s)
        if error:
            self.errors += 1
        if status is not None:
            self.statuses[status] = self.statuses.get(status, 0) + 1

    def percentile(self, p: float) -> float | None:
        if not self.samples:
            return None
        ordered = sorted(self.samples)
        if len(ordered) == 1:
            return ordered[0]
        # Nearest-rank style for small N.
        idx = min(len(ordered) - 1, max(0, int(round(p * (len(ordered) - 1)))))
        return ordered[idx]

    def summary(self) -> dict[str, float | int | None]:
        return {
            "n": len(self.samples),
            "errors": self.errors,
            "p50_s": self.percentile(0.50),
            "p95_s": self.percentile(0.95),
            "p99_s": self.percentile(0.99),
            "mean_s": statistics.fmean(self.samples) if self.samples else None,
        }


def _require_base_url() -> str:
    base = (os.environ.get("LOAD_TEST_BASE_URL") or "").strip().rstrip("/")
    if not base:
        raise SystemExit(
            "LOAD_TEST_BASE_URL is required. Point it at a disposable stack only."
        )
    parsed = urlparse(base)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise SystemExit(f"LOAD_TEST_BASE_URL is not a valid http(s) URL: {base!r}")

    port = parsed.port
    if port is None:
        port = 443 if parsed.scheme == "https" else 80

    allow_local = os.environ.get("LOAD_TEST_ALLOW_LOCAL", "").strip() == "1"
    if port in _MAT_DEFAULT_PORTS and not allow_local:
        raise SystemExit(
            f"Refusing default MAT port {port} in LOAD_TEST_BASE_URL={base!r}. "
            "Use a disposable publish port, or set LOAD_TEST_ALLOW_LOCAL=1 for an "
            "intentional local disposable run (still do not use founder MAT DB / "
            "do not destroy MAT volumes)."
        )
    return base


def _auth_headers() -> dict[str, str]:
    token = (os.environ.get("LOAD_TEST_AUTH_TOKEN") or "").strip()
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}


async def _timed_get(
    client: httpx.AsyncClient, url: str, stats: LatencyStats
) -> None:
    started = time.perf_counter()
    status: int | None = None
    error = False
    try:
        response = await client.get(url, headers=_auth_headers())
        status = response.status_code
        if status >= 500:
            error = True
    except httpx.HTTPError:
        error = True
    stats.add(time.perf_counter() - started, status, error)


async def _timed_post_multipart(
    client: httpx.AsyncClient,
    url: str,
    stats: LatencyStats,
    *,
    field_name: str = "file",
) -> None:
    started = time.perf_counter()
    status: int | None = None
    error = False
    # Minimal PDF header bytes — disposable upload pressure only.
    pdf_bytes = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
    try:
        response = await client.post(
            url,
            headers=_auth_headers(),
            files={field_name: ("load-test.pdf", pdf_bytes, "application/pdf")},
        )
        status = response.status_code
        # 4xx may be auth/validation on scaffolding; still counted. 5xx = error.
        if status >= 500:
            error = True
    except httpx.HTTPError:
        error = True
    stats.add(time.perf_counter() - started, status, error)


_BASELINE_LIST_PATHS = (
    "/api/v1/submissions",
    "/api/v1/students",
    "/api/v1/assessments",
)


async def run_scenario(
    *,
    base: str,
    scenario: str,
    concurrency: int,
    requests: int,
    list_path: str,
    list_paths: list[str],
    upload_path: str,
    health_path: str,
) -> LatencyStats:
    stats = LatencyStats()
    sem = asyncio.Semaphore(max(1, concurrency))
    timeout = httpx.Timeout(60.0, connect=10.0)

    async with httpx.AsyncClient(base_url=base, timeout=timeout) as client:

        async def one(i: int) -> None:
            async with sem:
                if scenario == "uploads":
                    await _timed_post_multipart(client, upload_path, stats)
                elif scenario == "list":
                    await _timed_get(client, list_path, stats)
                elif scenario == "health":
                    await _timed_get(client, health_path, stats)
                elif scenario == "baseline":
                    # Rotate health + authenticated list endpoints for p50/p95/p99.
                    paths = [health_path, *list_paths]
                    await _timed_get(client, paths[i % len(paths)], stats)
                else:
                    raise SystemExit(f"Unknown scenario: {scenario}")

        await asyncio.gather(*(one(i) for i in range(requests)))
    return stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="EduVijna disposable load scaffolding")
    parser.add_argument(
        "--scenario",
        choices=["baseline", "uploads", "list", "health"],
        required=True,
        help=(
            "baseline=health + list endpoints; uploads≈30 concurrent; "
            "list=single list path; health=liveness pressure"
        ),
    )
    parser.add_argument("--concurrency", type=int, default=30)
    parser.add_argument(
        "--requests",
        type=int,
        default=0,
        help="Total requests (defaults: baseline=120, uploads=30, list=120, health=200)",
    )
    parser.add_argument(
        "--list-path",
        default="/api/v1/submissions",
        help="Path for listing pressure (auth may be required)",
    )
    parser.add_argument(
        "--list-paths",
        default=",".join(_BASELINE_LIST_PATHS),
        help="Comma-separated list paths for --scenario baseline",
    )
    parser.add_argument(
        "--upload-path",
        default="/api/v1/submissions",
        help="Upload path POST multipart (auth + assessment_id form field required)",
    )
    parser.add_argument("--health-path", default="/health")
    args = parser.parse_args(argv)

    base = _require_base_url()
    defaults = {"baseline": 120, "uploads": 30, "list": 120, "health": 200}
    total = args.requests or defaults[args.scenario]
    concurrency = args.concurrency
    if args.scenario == "uploads" and args.requests == 0:
        concurrency = min(concurrency, 30)
    list_paths = [p.strip() for p in str(args.list_paths).split(",") if p.strip()]
    if not list_paths:
        list_paths = list(_BASELINE_LIST_PATHS)

    print(f"LOAD_TEST_BASE_URL={base}")
    print(
        f"scenario={args.scenario} concurrency={concurrency} requests={total} "
        f"(SLOs PROVISIONAL — see docs/production/PERFORMANCE_RELIABILITY.md)"
    )

    stats = asyncio.run(
        run_scenario(
            base=base,
            scenario=args.scenario,
            concurrency=concurrency,
            requests=total,
            list_path=args.list_path,
            list_paths=list_paths,
            upload_path=args.upload_path,
            health_path=args.health_path,
        )
    )
    summary = stats.summary()
    print(
        "latency_s "
        f"p50={summary['p50_s']:.4f} "
        f"p95={summary['p95_s']:.4f} "
        f"p99={summary['p99_s']:.4f} "
        f"mean={summary['mean_s']:.4f} "
        f"n={summary['n']} errors={summary['errors']}"
        if summary["n"]
        else "no samples"
    )
    print(f"status_counts={dict(sorted(stats.statuses.items()))}")
    print(
        "NOTES: worker restart / Redis / object storage / AI timeout / DB pressure "
        "are documented in infra/load/README.md — run only on disposable stacks."
    )
    return 0 if summary["errors"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

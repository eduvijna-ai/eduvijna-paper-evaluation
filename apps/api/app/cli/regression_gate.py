"""CLI release gate for B15 gold benchmark regression runs.

Usage:
    python -m app.cli.regression_gate --run-id UUID [--tenant-id UUID]

Exit 0 if gate passed, exit 1 otherwise. Prints JSON verdict to stdout.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from typing import Any

from sqlalchemy import select

from app.db.models import BenchmarkRegressionRun, Tenant
from app.db.session import async_session_factory
from app.services.benchmark import BenchmarkError, evaluate_release_gate


async def _resolve_tenant_id(
    *, run_id: uuid.UUID, tenant_id: uuid.UUID | None
) -> uuid.UUID:
    async with async_session_factory() as db:
        if tenant_id is not None:
            return tenant_id
        run = await db.scalar(
            select(BenchmarkRegressionRun).where(BenchmarkRegressionRun.id == run_id)
        )
        if run is None:
            # Fall back to demo tenant only for clearer NOT_FOUND from service path
            demo = await db.scalar(select(Tenant).where(Tenant.slug == "demo"))
            if demo is None:
                raise SystemExit(
                    json.dumps(
                        {
                            "passed": False,
                            "verdict": "FAIL",
                            "error": "run_not_found",
                            "run_id": str(run_id),
                        }
                    )
                )
            return demo.id
        return run.tenant_id


async def _run(run_id: uuid.UUID, tenant_id: uuid.UUID | None) -> dict[str, Any]:
    resolved_tenant = await _resolve_tenant_id(run_id=run_id, tenant_id=tenant_id)
    async with async_session_factory() as db:
        try:
            result = await evaluate_release_gate(
                db,
                tenant_id=resolved_tenant,
                run_id=run_id,
                actor_user_id=None,
            )
            await db.commit()
            return result
        except BenchmarkError as exc:
            await db.rollback()
            return {
                "passed": False,
                "verdict": "FAIL",
                "error": exc.code,
                "message": exc.message,
                "run_id": str(run_id),
            }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="B15 regression release gate")
    parser.add_argument("--run-id", required=True, type=uuid.UUID)
    parser.add_argument("--tenant-id", required=False, type=uuid.UUID, default=None)
    args = parser.parse_args(argv)
    result = asyncio.run(_run(args.run_id, args.tenant_id))
    print(json.dumps(result, sort_keys=True, default=str))
    return 0 if result.get("passed") else 1


if __name__ == "__main__":
    sys.exit(main())

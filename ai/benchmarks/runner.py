#!/usr/bin/env python3
"""PREPROD-003 AI quality harness runner (fixed provider + safe fixtures).

Usage:
  python ai/benchmarks/runner.py --manifest ai/benchmarks/manifests/v1/fixtures.safe.json

Does not claim real-paper PASS. OpenAI mode is refused without explicit opt-in
and remains gated by AI_PRODUCTION_PROVIDER_GATE.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve().parent
_AI_ROOT = _HERE.parent
for candidate in (_HERE, _AI_ROOT):
    path_s = str(candidate)
    if path_s not in sys.path:
        sys.path.insert(0, path_s)

try:
    from benchmarks.report import (  # type: ignore[import-not-found]
        REAL_PAPER_CORPUS_GATE,
        build_report_payload,
        write_report,
    )
    from benchmarks.scoring import (  # type: ignore[import-not-found]
        SUPPORTED_CATEGORIES,
        aggregate_metrics,
        score_case,
    )
except ImportError:  # pragma: no cover — script execution from ai/benchmarks/
    from report import (  # type: ignore[no-redef]
        REAL_PAPER_CORPUS_GATE,
        build_report_payload,
        write_report,
    )
    from scoring import (  # type: ignore[no-redef]
        SUPPORTED_CATEGORIES,
        aggregate_metrics,
        score_case,
    )


def load_manifest(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"}:
        try:
            import yaml  # type: ignore[import-untyped]
        except ImportError as exc:  # pragma: no cover
            raise SystemExit(
                "PyYAML is required for YAML manifests; use fixtures.safe.json or "
                "install PyYAML."
            ) from exc
        data = yaml.safe_load(text)
    else:
        data = json.loads(text)
    if not isinstance(data, dict):
        raise SystemExit("Manifest root must be an object")
    return data


def validate_manifest(manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if manifest.get("manifest_version") != "1":
        errors.append("manifest_version must be '1'")
    if not manifest.get("name"):
        errors.append("name is required")
    cases = manifest.get("cases")
    if not isinstance(cases, list) or not cases:
        errors.append("cases must be a non-empty array")
        return errors
    for case in cases:
        if not isinstance(case, dict):
            errors.append("case must be an object")
            continue
        case_id = case.get("id")
        if not case_id:
            errors.append("case.id is required")
        categories = case.get("categories") or []
        unknown = set(categories) - SUPPORTED_CATEGORIES
        if unknown:
            errors.append(f"case {case_id}: unsupported categories {sorted(unknown)}")
        if "gold" not in case:
            errors.append(f"case {case_id}: gold is required")
    return errors


def predict_fixed(case: dict[str, Any]) -> dict[str, Any]:
    prediction = case.get("fixed_prediction")
    if not isinstance(prediction, dict):
        raise ValueError(
            f"case {case.get('id')}: fixed_prediction required for --provider fixed"
        )
    return prediction


def run_harness(
    *,
    manifest: dict[str, Any],
    provider: str,
) -> dict[str, Any]:
    if provider != "fixed":
        raise SystemExit(
            f"Provider {provider!r} is not enabled in scaffolding. "
            "Use --provider fixed. Production OpenAI remains "
            "AI_PRODUCTION_PROVIDER_GATE=EXTERNAL_INPUT_REQUIRED."
        )

    case_results: list[dict[str, Any]] = []
    scores: list[dict[str, float]] = []
    for case in manifest["cases"]:
        case_id = str(case["id"])
        try:
            prediction = predict_fixed(case)
            metrics = score_case(gold=case.get("gold") or {}, prediction=prediction)
            scores.append(metrics)
            case_results.append(
                {
                    "id": case_id,
                    "status": "SCORED",
                    "categories": list(case.get("categories") or []),
                    "metrics": metrics,
                }
            )
        except Exception as exc:  # noqa: BLE001 — isolate per-case failures
            case_results.append(
                {
                    "id": case_id,
                    "status": "FAILED",
                    "categories": list(case.get("categories") or []),
                    "error": str(exc)[:500],
                }
            )

    report = build_report_payload(
        manifest_name=str(manifest.get("name")),
        provider=provider,
        case_results=case_results,
        aggregate=aggregate_metrics(scores),
        real_paper_corpus=bool(manifest.get("real_paper_corpus")),
    )
    # Hard stop: scaffolding never claims real-paper PASS.
    report["real_paper_pass"] = False
    report["gates"]["REAL_PAPER_CORPUS_GATE"] = REAL_PAPER_CORPUS_GATE
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="EduVijna AI quality harness runner")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=_HERE / "manifests" / "v1" / "fixtures.safe.json",
        help="Path to manifest JSON/YAML",
    )
    parser.add_argument(
        "--provider",
        choices=["fixed"],
        default="fixed",
        help="Only fixed is supported in scaffolding (safe / credential-free)",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=_HERE / "results",
        help="Directory for generated reports",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate manifest and exit without scoring",
    )
    args = parser.parse_args(argv)

    manifest = load_manifest(args.manifest)
    errors = validate_manifest(manifest)
    if errors:
        for err in errors:
            print(f"ERROR: {err}", file=sys.stderr)
        return 2
    if args.validate_only:
        print(f"OK: manifest {manifest.get('name')!r} validated")
        print(f"REAL_PAPER_CORPUS_GATE={REAL_PAPER_CORPUS_GATE}")
        return 0

    report = run_harness(manifest=manifest, provider=args.provider)
    stem = f"{manifest.get('name', 'harness')}-{args.provider}"
    json_path, md_path = write_report(report, args.out_dir, stem=stem)
    print(f"harness_ok={report['harness_ok']} real_paper_pass={report['real_paper_pass']}")
    print(f"REAL_PAPER_CORPUS_GATE={REAL_PAPER_CORPUS_GATE}")
    print(f"wrote {json_path}")
    print(f"wrote {md_path}")
    return 0 if report["harness_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

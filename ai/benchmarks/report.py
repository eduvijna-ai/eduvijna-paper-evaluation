"""Result report writer for the PREPROD-003 AI quality harness."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


REAL_PAPER_CORPUS_GATE = "EXTERNAL_INPUT_REQUIRED"


def build_report_payload(
    *,
    manifest_name: str,
    provider: str,
    case_results: list[dict[str, Any]],
    aggregate: dict[str, float | None],
    real_paper_corpus: bool,
) -> dict[str, Any]:
    """Build a structured report. Never claims real-paper PASS while gate is open."""
    harness_ok = bool(case_results) and all(
        case.get("status") == "SCORED" for case in case_results
    )
    real_paper_pass = False
    if real_paper_corpus and REAL_PAPER_CORPUS_GATE != "EXTERNAL_INPUT_REQUIRED":
        # Gate must still be flipped by humans/docs; scaffolding keeps this false.
        real_paper_pass = False

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "manifest_name": manifest_name,
        "provider": provider,
        "harness_ok": harness_ok,
        "real_paper_pass": real_paper_pass,
        "gates": {
            "REAL_PAPER_CORPUS_GATE": REAL_PAPER_CORPUS_GATE,
            "AI_PRODUCTION_PROVIDER_GATE": "EXTERNAL_INPUT_REQUIRED",
        },
        "aggregate_metrics": aggregate,
        "cases": case_results,
        "notes": [
            "Synthetic/fixed-provider success proves harness wiring only.",
            "Do not interpret harness_ok as real-paper PASS.",
        ],
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# AI quality harness result",
        "",
        f"- Generated at: `{report.get('generated_at')}`",
        f"- Manifest: `{report.get('manifest_name')}`",
        f"- Provider: `{report.get('provider')}`",
        f"- Harness OK (wiring): **{report.get('harness_ok')}**",
        f"- Real-paper PASS: **{report.get('real_paper_pass')}**",
        f"- REAL_PAPER_CORPUS_GATE: `{report.get('gates', {}).get('REAL_PAPER_CORPUS_GATE')}`",
        f"- AI_PRODUCTION_PROVIDER_GATE: `{report.get('gates', {}).get('AI_PRODUCTION_PROVIDER_GATE')}`",
        "",
        "## Aggregate metrics",
        "",
    ]
    for key, value in (report.get("aggregate_metrics") or {}).items():
        rendered = "n/a" if value is None else f"{value:.4f}"
        lines.append(f"- `{key}`: {rendered}")
    lines.extend(["", "## Cases", ""])
    for case in report.get("cases") or []:
        lines.append(
            f"- `{case.get('id')}` status={case.get('status')} "
            f"categories={case.get('categories')}"
        )
    lines.extend(
        [
            "",
            "## Notes",
            "",
            *[f"- {note}" for note in report.get("notes") or []],
            "",
        ]
    )
    return "\n".join(lines)


def write_report(report: dict[str, Any], out_dir: Path, *, stem: str) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"{stem}.json"
    md_path = out_dir / f"{stem}.md"
    json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, md_path

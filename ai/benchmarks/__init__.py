"""PREPROD-003 AI quality harness package (offline metrics; extends B15, does not replace it)."""

from .report import REAL_PAPER_CORPUS_GATE, build_report_payload, write_report
from .scoring import METRIC_KEYS, SUPPORTED_CATEGORIES, aggregate_metrics, score_case

__all__ = [
    "METRIC_KEYS",
    "REAL_PAPER_CORPUS_GATE",
    "SUPPORTED_CATEGORIES",
    "aggregate_metrics",
    "build_report_payload",
    "score_case",
    "write_report",
]

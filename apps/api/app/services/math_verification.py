"""Deterministic SymPy math verification (B6). Never uses eval()."""

from __future__ import annotations

import ast
import re
from decimal import Decimal
from typing import Any

from app.ai.types import MathVerificationResult

_MAX_EXPR_LEN = 256
_MAX_SYMBOLS = 16
_ALLOWED_BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.Mod, ast.FloorDiv)
_ALLOWED_UNARY = (ast.UAdd, ast.USub)
_SAFE_NAMES = frozenset(
    {
        "x",
        "y",
        "z",
        "a",
        "b",
        "c",
        "n",
        "t",
        "pi",
        "e",
        "sin",
        "cos",
        "tan",
        "sqrt",
        "log",
        "ln",
        "exp",
        "Abs",
        "abs",
    }
)
_EXPR_RE = re.compile(r"^[0-9a-zA-Z_+\-*/^().\s=,]+$")


def _read_tolerance(structured_answer: dict[str, Any] | None) -> Decimal:
    if not structured_answer:
        return Decimal("1e-6")
    raw = structured_answer.get("tolerance", structured_answer.get("numeric_tolerance"))
    if raw is None:
        return Decimal("1e-6")
    try:
        tol = Decimal(str(raw))
    except Exception:
        return Decimal("1e-6")
    if tol < 0 or tol > 1:
        return Decimal("1e-6")
    return tol


def _ast_ok(expr: str) -> bool:
    if len(expr) > _MAX_EXPR_LEN or not _EXPR_RE.match(expr):
        return False
    try:
        tree = ast.parse(expr.replace("^", "**"), mode="eval")
    except SyntaxError:
        return False

    symbols: set[str] = set()

    class _Visitor(ast.NodeVisitor):
        def generic_visit(self, node: ast.AST) -> None:
            if isinstance(
                node,
                (
                    ast.Expression,
                    ast.Constant,
                    ast.Load,
                    ast.Store,
                    ast.Call,
                    ast.Name,
                    ast.BinOp,
                    ast.UnaryOp,
                    ast.Compare,
                    ast.Eq,
                    ast.NotEq,
                    ast.Lt,
                    ast.LtE,
                    ast.Gt,
                    ast.GtE,
                    *_ALLOWED_BINOPS,
                    *_ALLOWED_UNARY,
                ),
            ):
                if isinstance(node, ast.BinOp) and not isinstance(node.op, _ALLOWED_BINOPS):
                    raise ValueError("disallowed operator")
                if isinstance(node, ast.UnaryOp) and not isinstance(node.op, _ALLOWED_UNARY):
                    raise ValueError("disallowed unary")
                if isinstance(node, ast.Name):
                    if node.id not in _SAFE_NAMES:
                        raise ValueError("disallowed name")
                    symbols.add(node.id)
                if isinstance(node, ast.Call):
                    if not isinstance(node.func, ast.Name) or node.func.id not in _SAFE_NAMES:
                        raise ValueError("disallowed call")
                super().generic_visit(node)
                return
            if isinstance(node, (ast.Attribute, ast.Subscript, ast.Lambda, ast.List, ast.Dict)):
                raise ValueError("disallowed construct")
            raise ValueError(f"disallowed node {type(node).__name__}")

    try:
        _Visitor().visit(tree)
    except ValueError:
        return False
    return len(symbols) <= _MAX_SYMBOLS


def _parse_sympy(expr: str) -> Any | None:
    if not _ast_ok(expr):
        return None
    try:
        import sympy
        from sympy.parsing.sympy_parser import (
            convert_xor,
            implicit_multiplication_application,
            parse_expr,
            standard_transformations,
        )
    except ImportError:
        return None

    local_dict = {
        "pi": sympy.pi,
        "e": sympy.E,
        "sin": sympy.sin,
        "cos": sympy.cos,
        "tan": sympy.tan,
        "sqrt": sympy.sqrt,
        "log": sympy.log,
        "ln": sympy.log,
        "exp": sympy.exp,
        "Abs": sympy.Abs,
        "abs": sympy.Abs,
    }
    transformations = standard_transformations + (
        implicit_multiplication_application,
        convert_xor,
    )
    try:
        # AST gate already ran; avoid empty global_dict (breaks Integer/etc.).
        return parse_expr(
            expr,
            local_dict=local_dict,
            transformations=transformations,
            evaluate=True,
        )
    except Exception:
        return None


def verify_math(
    *,
    student_expr: str | None,
    expected_expr: str | None,
    structured_answer: dict[str, Any] | None = None,
) -> MathVerificationResult:
    """Compare student/expected expressions via SymPy. Failures never auto-zero."""
    if not student_expr or not expected_expr:
        return MathVerificationResult(
            equivalent=None,
            normalized_student=None,
            normalized_expected=None,
            math_verification_confidence=None,
            failure_reason="missing_expression",
        )

    student = student_expr.strip()
    expected = expected_expr.strip()
    if len(student) > _MAX_EXPR_LEN or len(expected) > _MAX_EXPR_LEN:
        return MathVerificationResult(
            equivalent=None,
            math_verification_confidence=Decimal("0.1000"),
            failure_reason="expression_too_long",
        )

    # Prefer structured equivalents when present.
    equivalents: list[str] = [expected]
    if structured_answer:
        extra = structured_answer.get("accepted_equivalent_expressions") or structured_answer.get(
            "equivalents"
        )
        if isinstance(extra, list):
            equivalents.extend(str(x) for x in extra if x is not None)

    student_parsed = _parse_sympy(student)
    if student_parsed is None:
        return MathVerificationResult(
            equivalent=None,
            normalized_student=None,
            normalized_expected=None,
            math_verification_confidence=Decimal("0.2000"),
            failure_reason="parse_failure_student",
        )

    tolerance = _read_tolerance(structured_answer)
    try:
        import sympy
    except ImportError:
        return MathVerificationResult(
            equivalent=None,
            math_verification_confidence=None,
            failure_reason="sympy_unavailable",
        )

    for cand in equivalents:
        expected_parsed = _parse_sympy(str(cand))
        if expected_parsed is None:
            continue
        try:
            diff = sympy.simplify(student_parsed - expected_parsed)
            if diff == 0:
                return MathVerificationResult(
                    equivalent=True,
                    normalized_student=str(student_parsed),
                    normalized_expected=str(expected_parsed),
                    math_verification_confidence=Decimal("0.9900"),
                    failure_reason=None,
                )
            if diff.is_number:
                if abs(float(diff)) <= float(tolerance):
                    return MathVerificationResult(
                        equivalent=True,
                        normalized_student=str(student_parsed),
                        normalized_expected=str(expected_parsed),
                        math_verification_confidence=Decimal("0.9500"),
                        failure_reason=None,
                    )
        except Exception:
            continue

    return MathVerificationResult(
        equivalent=False,
        normalized_student=str(student_parsed),
        normalized_expected=str(_parse_sympy(expected) or expected),
        math_verification_confidence=Decimal("0.7000"),
        failure_reason="not_equivalent",
    )

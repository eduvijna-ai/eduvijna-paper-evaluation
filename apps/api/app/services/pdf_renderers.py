"""PyMuPDF renderers for B7 annotated paper and report PDFs."""

from __future__ import annotations

from typing import Any

import fitz


def _ensure_pdf(data: bytes) -> bytes:
    if not data.startswith(b"%PDF"):
        raise ValueError("renderer did not produce a PDF")
    return data


def _draw_annotation(page: fitz.Page, ann: dict[str, Any]) -> None:
    """Draw a normalized annotation onto a page (coords in [0,1])."""
    rect = page.rect
    x = float(ann["x"]) * rect.width
    y = float(ann["y"]) * rect.height
    w = float(ann["width"]) * rect.width
    h = float(ann["height"]) * rect.height
    box = fitz.Rect(x, y, x + w, y + h)
    atype = str(ann.get("annotation_type") or "")
    payload = ann.get("payload") or {}

    color_map = {
        "TICK": (0.05, 0.55, 0.2),
        "CROSS": (0.75, 0.1, 0.1),
        "PARTIAL": (0.85, 0.55, 0.05),
        "MARK": (0.1, 0.2, 0.7),
        "COMMENT": (0.35, 0.35, 0.35),
        "HIGHLIGHT": (1.0, 0.95, 0.4),
    }
    color = color_map.get(atype, (0.2, 0.2, 0.2))

    if atype == "HIGHLIGHT":
        shape = page.new_shape()
        shape.draw_rect(box)
        shape.finish(color=None, fill=color, fill_opacity=0.35)
        shape.commit()
        return

    if atype == "TICK":
        # Simple checkmark
        p1 = fitz.Point(box.x0 + w * 0.15, box.y0 + h * 0.55)
        p2 = fitz.Point(box.x0 + w * 0.4, box.y0 + h * 0.8)
        p3 = fitz.Point(box.x0 + w * 0.85, box.y0 + h * 0.2)
        page.draw_line(p1, p2, color=color, width=2)
        page.draw_line(p2, p3, color=color, width=2)
    elif atype == "CROSS":
        page.draw_line(
            fitz.Point(box.x0, box.y0),
            fitz.Point(box.x1, box.y1),
            color=color,
            width=2,
        )
        page.draw_line(
            fitz.Point(box.x0, box.y1),
            fitz.Point(box.x1, box.y0),
            color=color,
            width=2,
        )
    elif atype == "PARTIAL":
        page.draw_rect(box, color=color, width=1.5)
        page.insert_text(
            fitz.Point(box.x0 + 2, box.y0 + min(12, h - 1)),
            "½",
            fontsize=min(14, max(8, h * 0.6)),
            color=color,
        )
    else:
        page.draw_rect(box, color=color, width=1)

    label_parts: list[str] = []
    if atype == "MARK":
        final = payload.get("final_marks")
        max_m = payload.get("max_marks")
        if final is not None and max_m is not None:
            label_parts.append(f"{final}/{max_m}")
        elif final is not None:
            label_parts.append(str(final))
    text = payload.get("text") or payload.get("reason")
    if text:
        label_parts.append(str(text)[:80])
    if label_parts:
        page.insert_textbox(
            box,
            " ".join(label_parts),
            fontsize=8,
            color=color,
            align=fitz.TEXT_ALIGN_LEFT,
        )


def render_evaluated_paper(
    pages: list[bytes],
    annotations: list[dict[str, Any]],
    *,
    page_id_by_index: list[str] | None = None,
) -> bytes:
    """Overlay ledger/human annotations on page images → multi-page PDF."""
    doc = fitz.open()
    try:
        page_index_by_id: dict[str, int] = {}
        if page_id_by_index:
            page_index_by_id = {pid: i for i, pid in enumerate(page_id_by_index)}

        for img_bytes in pages:
            # Create page sized to image
            pix = fitz.Pixmap(img_bytes)
            try:
                page = doc.new_page(width=pix.width, height=pix.height)
                page.insert_image(page.rect, pixmap=pix)
            finally:
                pix = None  # noqa: F841 — release

        for ann in annotations:
            page_id = str(ann.get("submission_page_id") or "")
            idx = page_index_by_id.get(page_id, 0)
            if idx < 0 or idx >= doc.page_count:
                idx = 0
            _draw_annotation(doc[idx], ann)

        out = doc.tobytes()
    finally:
        doc.close()
    return _ensure_pdf(out)


def _report_doc(title: str, lines: list[str]) -> bytes:
    doc = fitz.open()
    try:
        page = doc.new_page(width=595, height=842)  # A4
        y = 50.0
        page.insert_text(fitz.Point(50, y), title, fontsize=16, color=(0.1, 0.1, 0.2))
        y += 28
        for line in lines:
            if y > 800:
                page = doc.new_page(width=595, height=842)
                y = 50.0
            # wrap roughly
            chunk = line if len(line) <= 95 else line[:92] + "..."
            page.insert_text(fitz.Point(50, y), chunk, fontsize=10, color=(0.15, 0.15, 0.15))
            y += 14
        out = doc.tobytes()
    finally:
        doc.close()
    return _ensure_pdf(out)


def render_student_report_pdf(payload: dict[str, Any]) -> bytes:
    student = payload.get("student") or {}
    assessment = payload.get("assessment") or {}
    lines = [
        f"Student: {student.get('display_name', '')}",
        f"Assessment: {assessment.get('title', '')}",
        f"Score: {payload.get('total_score')} / {payload.get('max_total_score')} "
        f"({payload.get('percentage')}%)",
        f"Narrative source: {payload.get('narrative_source')}",
        "",
        "Strengths:",
        *[f"  - {s}" for s in (payload.get("strengths") or [])],
        "Areas for improvement:",
        *[f"  - {s}" for s in (payload.get("areas_for_improvement") or [])],
        "Next steps:",
        *[f"  - {s}" for s in (payload.get("next_steps") or [])],
        "",
        "Questions:",
    ]
    for q in payload.get("questions") or []:
        lines.append(
            f"  Q{q.get('question_code')}: {q.get('final_score')}/{q.get('max_mark')}"
        )
        if q.get("feedback"):
            lines.append(f"    Feedback: {q['feedback']}")
        if q.get("explanation"):
            lines.append(f"    Explanation: {q['explanation']}")
        for err in q.get("error_explanations") or []:
            lines.append(f"    Error: {err}")
    lines.append(f"Ledger snapshot: {payload.get('ledger_snapshot_hash')}")
    return _report_doc("Student Evaluation Report", lines)


def render_parent_report_pdf(payload: dict[str, Any]) -> bytes:
    lines = [
        f"Student: {payload.get('student_display_name', '')}",
        f"Assessment: {payload.get('assessment_title', '')}",
        f"Score: {payload.get('total_score')} / {payload.get('max_total_score')} "
        f"({payload.get('percentage')}%)",
    ]
    if payload.get("score_summary"):
        lines.append(str(payload["score_summary"]))
    lines.append("")
    lines.append("What went well:")
    lines.extend(f"  - {s}" for s in (payload.get("what_went_well") or []))
    lines.append("What to practice:")
    lines.extend(f"  - {s}" for s in (payload.get("what_to_practice") or []))
    lines.append("How family can help:")
    lines.extend(f"  - {s}" for s in (payload.get("how_family_can_help") or []))
    lines.append(f"Next step: {payload.get('next_step', '')}")
    lines.append(f"Ledger snapshot: {payload.get('ledger_snapshot_hash')}")
    return _report_doc("Parent Report", lines)


def render_teacher_report_pdf(payload: dict[str, Any]) -> bytes:
    student = payload.get("student") or {}
    assessment = payload.get("assessment") or {}
    lines = [
        f"Student: {student.get('display_name', '')}",
        f"Assessment: {assessment.get('title', '')}",
        f"Score: {payload.get('total_score')} / {payload.get('max_total_score')}",
        "",
        "Diagnostic detail:",
    ]
    for q in payload.get("questions") or []:
        lines.append(
            f"  Q{q.get('question_code')}: {q.get('final_score')}/{q.get('max_mark')} "
            f"[{q.get('workflow_state')}]"
        )
        lines.append(f"    Errors: {', '.join(q.get('error_codes') or []) or 'none'}")
        conf = q.get("confidences") or {}
        lines.append(
            "    Confidences: "
            f"id={conf.get('identity')} map={conf.get('mapping')} "
            f"tr={conf.get('transcription')} ev={conf.get('evaluation')} "
            f"math={conf.get('math_verification')}"
        )
        for c in q.get("criterion_decisions") or []:
            lines.append(
                f"    Criterion {c.get('criterion_code')}: "
                f"{c.get('final_marks')}/{c.get('max_marks')} ({c.get('decision')})"
            )
        for a in q.get("review_actions") or []:
            lines.append(
                f"    Review {a.get('action_type')}: "
                f"{a.get('previous_score')} → {a.get('new_score')}"
            )
    lines.append(f"Ledger snapshot: {payload.get('ledger_snapshot_hash')}")
    return _report_doc("Teacher Diagnostic Report", lines)

"""B9_V1 learning algorithm unit tests (pure, no DB)."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from app.services.learning_algorithm import (
    EvidenceFact,
    LearningError,
    NodeMeta,
    PrerequisiteEdge,
    aggregate_node_signals,
    build_learning_plan_structure,
    compute_curriculum_graph_hash,
    compute_input_hash,
    compute_source_evidence_hash,
    contains_url_like,
)


def _nid() -> uuid.UUID:
    return uuid.uuid4()


def _fact(
    *,
    node_id: uuid.UUID,
    evidence_type: str,
    strength: str,
    score: str = "0.500000",
    reasons: list[str] | None = None,
    academic: list[str] | None = None,
    review: list[str] | None = None,
) -> EvidenceFact:
    return EvidenceFact(
        id=uuid.uuid4(),
        published_result_id=uuid.uuid4(),
        question_evaluation_id=uuid.uuid4(),
        curriculum_node_id=node_id,
        evidence_type=evidence_type,
        strength=strength,
        score_ratio=Decimal(score),
        academic_error_codes=academic or [],
        review_condition_codes=review or [],
        reason_codes=reasons or [],
        source_ledger_snapshot_hash="a" * 64,
        algorithm_version="B8_V1",
    )


def _node(code: str, title: str | None = None) -> NodeMeta:
    return NodeMeta(
        id=_nid(),
        code=code,
        title=title or code,
        node_type="CONCEPT",
        status="active",
    )


def test_concept_weak_target_concept_priority_1() -> None:
    node = _node("N1", "Quadratic")
    facts = [
        _fact(node_id=node.id, evidence_type="CONCEPT", strength="WEAK"),
        _fact(node_id=node.id, evidence_type="EXECUTION", strength="INCONCLUSIVE"),
        _fact(node_id=node.id, evidence_type="PROCEDURE", strength="INCONCLUSIVE"),
    ]
    plan = build_learning_plan_structure(
        curriculum_id=uuid.uuid4(), nodes=[node], edges=[], facts=facts
    )
    assert len(plan.recommendations) == 1
    rec = plan.recommendations[0]
    assert rec.recommendation_kind == "TARGET_CONCEPT"
    assert rec.priority == 1
    assert plan.path_steps[0].kind == "LEARN"


def test_procedure_weak_priority_2() -> None:
    node = _node("N2", "Factorisation")
    facts = [
        _fact(node_id=node.id, evidence_type="CONCEPT", strength="STRONG"),
        _fact(node_id=node.id, evidence_type="EXECUTION", strength="STRONG"),
        _fact(node_id=node.id, evidence_type="PROCEDURE", strength="WEAK"),
    ]
    plan = build_learning_plan_structure(
        curriculum_id=uuid.uuid4(), nodes=[node], edges=[], facts=facts
    )
    assert plan.recommendations[0].recommendation_kind == "PROCEDURE_PRACTICE"
    assert plan.recommendations[0].priority == 2


def test_execution_weak_not_concept_relearn() -> None:
    node = _node("N3", "Linear")
    facts = [
        _fact(node_id=node.id, evidence_type="CONCEPT", strength="STRONG"),
        _fact(node_id=node.id, evidence_type="EXECUTION", strength="WEAK"),
        _fact(node_id=node.id, evidence_type="PROCEDURE", strength="INCONCLUSIVE"),
    ]
    plan = build_learning_plan_structure(
        curriculum_id=uuid.uuid4(), nodes=[node], edges=[], facts=facts
    )
    assert len(plan.recommendations) == 1
    rec = plan.recommendations[0]
    assert rec.recommendation_kind == "EXECUTION_PRACTICE"
    assert rec.priority == 3
    assert rec.recommendation_kind != "TARGET_CONCEPT"
    assert "concept gap" not in rec.rationale.lower() or "execution" in rec.rationale.lower()


def test_inconclusive_blank_unreadable_no_weak_recommendation() -> None:
    node = _node("N4")
    facts = [
        _fact(
            node_id=node.id,
            evidence_type="CONCEPT",
            strength="INCONCLUSIVE",
            reasons=["BLANK"],
        ),
        _fact(
            node_id=node.id,
            evidence_type="EXECUTION",
            strength="INCONCLUSIVE",
            reasons=["BLANK"],
        ),
        _fact(
            node_id=node.id,
            evidence_type="PROCEDURE",
            strength="INCONCLUSIVE",
            reasons=["BLANK"],
        ),
        _fact(
            node_id=node.id,
            evidence_type="CONCEPT",
            strength="INCONCLUSIVE",
            review=["UNREADABLE"],
            reasons=["UNREADABLE"],
        ),
    ]
    plan = build_learning_plan_structure(
        curriculum_id=uuid.uuid4(), nodes=[node], edges=[], facts=facts
    )
    assert plan.recommendations == []
    assert plan.path_steps == []
    assert plan.no_gap_message is not None


def test_strong_only_no_remediation() -> None:
    node = _node("N5")
    facts = [
        _fact(node_id=node.id, evidence_type="CONCEPT", strength="STRONG"),
        _fact(node_id=node.id, evidence_type="EXECUTION", strength="STRONG"),
        _fact(node_id=node.id, evidence_type="PROCEDURE", strength="STRONG"),
    ]
    plan = build_learning_plan_structure(
        curriculum_id=uuid.uuid4(), nodes=[node], edges=[], facts=facts
    )
    assert plan.recommendations == []


def test_required_weak_prerequisite_before_target() -> None:
    prereq = _node("A", "Linear Equations")
    target = _node("B", "Quadratic Equations")
    edge = PrerequisiteEdge(
        id=uuid.uuid4(),
        prerequisite_node_id=prereq.id,
        dependent_node_id=target.id,
        relationship_type="REQUIRED",
    )
    facts = [
        _fact(node_id=prereq.id, evidence_type="CONCEPT", strength="WEAK"),
        _fact(node_id=prereq.id, evidence_type="EXECUTION", strength="INCONCLUSIVE"),
        _fact(node_id=prereq.id, evidence_type="PROCEDURE", strength="INCONCLUSIVE"),
        _fact(node_id=target.id, evidence_type="CONCEPT", strength="WEAK"),
        _fact(node_id=target.id, evidence_type="EXECUTION", strength="INCONCLUSIVE"),
        _fact(node_id=target.id, evidence_type="PROCEDURE", strength="INCONCLUSIVE"),
    ]
    plan = build_learning_plan_structure(
        curriculum_id=uuid.uuid4(),
        nodes=[prereq, target],
        edges=[edge],
        facts=facts,
    )
    kinds = [r.recommendation_kind for r in plan.recommendations]
    assert "PREREQUISITE_REPAIR" in kinds
    assert "TARGET_CONCEPT" in kinds
    # Path: prerequisite before target
    path_nodes = [s.curriculum_node_id for s in plan.path_steps]
    assert path_nodes.index(prereq.id) < path_nodes.index(target.id)
    assert plan.path_steps[0].kind == "PREREQUISITE"
    assert plan.path_steps[0].relationship_type == "REQUIRED"


def test_required_strong_prerequisite_omitted() -> None:
    prereq = _node("A", "Basics")
    target = _node("B", "Advanced")
    edge = PrerequisiteEdge(
        id=uuid.uuid4(),
        prerequisite_node_id=prereq.id,
        dependent_node_id=target.id,
        relationship_type="REQUIRED",
    )
    facts = [
        _fact(node_id=prereq.id, evidence_type="CONCEPT", strength="STRONG"),
        _fact(node_id=prereq.id, evidence_type="EXECUTION", strength="STRONG"),
        _fact(node_id=prereq.id, evidence_type="PROCEDURE", strength="STRONG"),
        _fact(node_id=target.id, evidence_type="CONCEPT", strength="WEAK"),
        _fact(node_id=target.id, evidence_type="EXECUTION", strength="INCONCLUSIVE"),
        _fact(node_id=target.id, evidence_type="PROCEDURE", strength="INCONCLUSIVE"),
    ]
    plan = build_learning_plan_structure(
        curriculum_id=uuid.uuid4(),
        nodes=[prereq, target],
        edges=[edge],
        facts=facts,
    )
    assert all(r.recommendation_kind != "PREREQUISITE_REPAIR" for r in plan.recommendations)
    assert not any(s.kind == "PREREQUISITE" for s in plan.path_steps)
    assert not any(s.kind == "MASTERY_CHECK" for s in plan.path_steps)


def test_required_inconclusive_mastery_check() -> None:
    prereq = _node("A", "Factorisation")
    target = _node("B", "Quadratics")
    edge = PrerequisiteEdge(
        id=uuid.uuid4(),
        prerequisite_node_id=prereq.id,
        dependent_node_id=target.id,
        relationship_type="REQUIRED",
    )
    facts = [
        _fact(node_id=prereq.id, evidence_type="CONCEPT", strength="INCONCLUSIVE"),
        _fact(node_id=prereq.id, evidence_type="EXECUTION", strength="INCONCLUSIVE"),
        _fact(node_id=prereq.id, evidence_type="PROCEDURE", strength="INCONCLUSIVE"),
        _fact(node_id=target.id, evidence_type="CONCEPT", strength="WEAK"),
        _fact(node_id=target.id, evidence_type="EXECUTION", strength="INCONCLUSIVE"),
        _fact(node_id=target.id, evidence_type="PROCEDURE", strength="INCONCLUSIVE"),
    ]
    plan = build_learning_plan_structure(
        curriculum_id=uuid.uuid4(),
        nodes=[prereq, target],
        edges=[edge],
        facts=facts,
    )
    assert all(r.target_node_id != prereq.id for r in plan.recommendations)
    assert any(
        s.kind == "MASTERY_CHECK" and s.curriculum_node_id == prereq.id
        for s in plan.path_steps
    )
    mastery_idx = next(
        i
        for i, s in enumerate(plan.path_steps)
        if s.kind == "MASTERY_CHECK" and s.curriculum_node_id == prereq.id
    )
    target_idx = next(
        i for i, s in enumerate(plan.path_steps) if s.curriculum_node_id == target.id
    )
    assert mastery_idx < target_idx


def test_recommended_weak_lower_priority() -> None:
    prereq = _node("A", "Support")
    target = _node("B", "Main")
    edge = PrerequisiteEdge(
        id=uuid.uuid4(),
        prerequisite_node_id=prereq.id,
        dependent_node_id=target.id,
        relationship_type="RECOMMENDED",
    )
    facts = [
        _fact(node_id=prereq.id, evidence_type="CONCEPT", strength="WEAK"),
        _fact(node_id=prereq.id, evidence_type="EXECUTION", strength="INCONCLUSIVE"),
        _fact(node_id=prereq.id, evidence_type="PROCEDURE", strength="INCONCLUSIVE"),
        _fact(node_id=target.id, evidence_type="CONCEPT", strength="WEAK"),
        _fact(node_id=target.id, evidence_type="EXECUTION", strength="INCONCLUSIVE"),
        _fact(node_id=target.id, evidence_type="PROCEDURE", strength="INCONCLUSIVE"),
    ]
    plan = build_learning_plan_structure(
        curriculum_id=uuid.uuid4(),
        nodes=[prereq, target],
        edges=[edge],
        facts=facts,
    )
    repair = next(
        r
        for r in plan.recommendations
        if r.target_node_id == prereq.id and r.recommendation_kind == "PREREQUISITE_REPAIR"
    )
    assert repair.priority == 2
    assert any(
        s.relationship_type == "RECOMMENDED" and s.curriculum_node_id == prereq.id
        for s in plan.path_steps
    )


def test_cycle_raises() -> None:
    a = _node("A")
    b = _node("B")
    edges = [
        PrerequisiteEdge(
            id=uuid.uuid4(),
            prerequisite_node_id=a.id,
            dependent_node_id=b.id,
            relationship_type="REQUIRED",
        ),
        PrerequisiteEdge(
            id=uuid.uuid4(),
            prerequisite_node_id=b.id,
            dependent_node_id=a.id,
            relationship_type="REQUIRED",
        ),
    ]
    facts = [
        _fact(node_id=b.id, evidence_type="CONCEPT", strength="WEAK"),
        _fact(node_id=b.id, evidence_type="EXECUTION", strength="INCONCLUSIVE"),
        _fact(node_id=b.id, evidence_type="PROCEDURE", strength="INCONCLUSIVE"),
    ]
    with pytest.raises(LearningError) as exc:
        build_learning_plan_structure(
            curriculum_id=uuid.uuid4(), nodes=[a, b], edges=edges, facts=facts
        )
    assert exc.value.code == "CURRICULUM_PREREQUISITE_CYCLE"


def test_hashes_deterministic_and_sensitive() -> None:
    node = _node("H1")
    facts = [
        _fact(node_id=node.id, evidence_type="CONCEPT", strength="WEAK"),
        _fact(node_id=node.id, evidence_type="EXECUTION", strength="INCONCLUSIVE"),
        _fact(node_id=node.id, evidence_type="PROCEDURE", strength="INCONCLUSIVE"),
    ]
    cid = uuid.uuid4()
    h1 = compute_source_evidence_hash(facts)
    h2 = compute_source_evidence_hash(list(reversed(facts)))
    assert h1 == h2
    graph1 = compute_curriculum_graph_hash(curriculum_id=cid, nodes=[node], edges=[])
    graph2 = compute_curriculum_graph_hash(curriculum_id=cid, nodes=[node], edges=[])
    assert graph1 == graph2
    input1 = compute_input_hash(source_evidence_hash=h1, curriculum_graph_hash=graph1)
    other = _node("H2")
    graph3 = compute_curriculum_graph_hash(
        curriculum_id=cid, nodes=[node, other], edges=[]
    )
    assert graph3 != graph1
    assert (
        compute_input_hash(source_evidence_hash=h1, curriculum_graph_hash=graph3)
        != input1
    )


def test_aggregate_and_url_guard() -> None:
    node = _node("AGG")
    facts = [
        _fact(node_id=node.id, evidence_type="CONCEPT", strength="WEAK"),
        _fact(node_id=node.id, evidence_type="CONCEPT", strength="STRONG"),
        _fact(node_id=node.id, evidence_type="EXECUTION", strength="WEAK"),
        _fact(node_id=node.id, evidence_type="PROCEDURE", strength="INCONCLUSIVE"),
    ]
    aggs = aggregate_node_signals(nodes=[node], facts=facts)
    # concept tie WEAK=1 STRONG=1 → INCONCLUSIVE; execution WEAK
    assert aggs[node.id].concept == "INCONCLUSIVE"
    assert aggs[node.id].execution == "WEAK"
    assert contains_url_like("see https://example.com")
    assert contains_url_like("www.evil.test")
    assert not contains_url_like("Review Linear Equations carefully.")

"""B9_V1 deterministic learning recommendation algorithm (server-authoritative)."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Literal

from app.services.mastery_derivation import Strength, aggregate_signal

ALGORITHM_VERSION = "B9_V1"
SOURCE_EVIDENCE_ALGORITHM = "B8_V1"

RecommendationKind = Literal[
    "PREREQUISITE_REPAIR",
    "TARGET_CONCEPT",
    "PROCEDURE_PRACTICE",
    "EXECUTION_PRACTICE",
]
PathStepKind = Literal[
    "PREREQUISITE",
    "LEARN",
    "GUIDED",
    "INDEPENDENT",
    "MASTERY_CHECK",
]
RelationshipType = Literal["REQUIRED", "RECOMMENDED"]


class LearningError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _canonical_hash(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class EvidenceFact:
    id: uuid.UUID
    published_result_id: uuid.UUID
    question_evaluation_id: uuid.UUID
    curriculum_node_id: uuid.UUID
    evidence_type: str
    strength: str
    score_ratio: Decimal
    academic_error_codes: list[str]
    review_condition_codes: list[str]
    reason_codes: list[str]
    source_ledger_snapshot_hash: str
    algorithm_version: str


@dataclass(frozen=True)
class NodeMeta:
    id: uuid.UUID
    code: str
    title: str
    node_type: str
    status: str


@dataclass(frozen=True)
class PrerequisiteEdge:
    id: uuid.UUID
    prerequisite_node_id: uuid.UUID
    dependent_node_id: uuid.UUID
    relationship_type: RelationshipType


@dataclass(frozen=True)
class NodeAggregate:
    node: NodeMeta
    concept: Strength
    execution: Strength
    procedure: Strength
    evidence_count: int
    weak_evidence_count: int
    mean_score_ratio: Decimal | None
    evidence_ids: tuple[uuid.UUID, ...]


@dataclass(frozen=True)
class PlannedPrerequisite:
    node_id: uuid.UUID
    relationship_type: RelationshipType
    sequence: int


@dataclass
class PlannedRecommendation:
    target_node_id: uuid.UUID
    recommendation_kind: RecommendationKind
    priority: Literal[1, 2, 3]
    rationale: str
    concept_signal: Strength
    execution_signal: Strength
    procedure_signal: Strength
    evidence_count: int
    mean_evidence_score_ratio: Decimal | None
    evidence_ids: tuple[uuid.UUID, ...]
    prerequisites: list[PlannedPrerequisite] = field(default_factory=list)
    target_node_code: str = ""
    target_node_title: str = ""
    target_node_type: str = ""
    # Stable key for path ordering / dedupe
    sort_key: tuple[Any, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class PlannedPathStep:
    curriculum_node_id: uuid.UUID
    kind: PathStepKind
    sequence: int
    title: str
    description: str
    evidence_basis: str
    relationship_type: RelationshipType | None
    recommendation_key: tuple[Any, ...] | None


@dataclass(frozen=True)
class LearningPlanStructure:
    source_evidence_hash: str
    curriculum_graph_hash: str
    input_hash: str
    recommendations: list[PlannedRecommendation]
    path_steps: list[PlannedPathStep]
    no_gap_message: str | None


def compute_source_evidence_hash(facts: list[EvidenceFact]) -> str:
    rows = []
    for f in sorted(
        [x for x in facts if x.algorithm_version == SOURCE_EVIDENCE_ALGORITHM],
        key=lambda e: str(e.id),
    ):
        rows.append(
            {
                "id": str(f.id),
                "published_result_id": str(f.published_result_id),
                "question_evaluation_id": str(f.question_evaluation_id),
                "curriculum_node_id": str(f.curriculum_node_id),
                "evidence_type": f.evidence_type,
                "strength": f.strength,
                "score_ratio": str(f.score_ratio),
                "academic_error_codes": sorted(f.academic_error_codes),
                "review_condition_codes": sorted(f.review_condition_codes),
                "reason_codes": sorted(f.reason_codes),
                "source_ledger_snapshot_hash": f.source_ledger_snapshot_hash,
                "algorithm_version": f.algorithm_version,
            }
        )
    return _canonical_hash(rows)


def compute_curriculum_graph_hash(
    *,
    curriculum_id: uuid.UUID,
    nodes: list[NodeMeta],
    edges: list[PrerequisiteEdge],
) -> str:
    node_rows = [
        {
            "id": str(n.id),
            "code": n.code,
            "title": n.title,
            "type": n.node_type,
            "status": n.status,
        }
        for n in sorted(nodes, key=lambda n: (n.code, str(n.id)))
    ]
    edge_rows = [
        {
            "id": str(e.id),
            "prerequisite_node_id": str(e.prerequisite_node_id),
            "dependent_node_id": str(e.dependent_node_id),
            "relationship_type": e.relationship_type,
        }
        for e in sorted(edges, key=lambda e: str(e.id))
    ]
    return _canonical_hash(
        {
            "curriculum_id": str(curriculum_id),
            "nodes": node_rows,
            "prerequisites": edge_rows,
        }
    )


def compute_input_hash(
    *, source_evidence_hash: str, curriculum_graph_hash: str
) -> str:
    return _canonical_hash(
        {
            "algorithm_version": ALGORITHM_VERSION,
            "source_evidence_hash": source_evidence_hash,
            "curriculum_graph_hash": curriculum_graph_hash,
        }
    )


def aggregate_node_signals(
    *,
    nodes: list[NodeMeta],
    facts: list[EvidenceFact],
) -> dict[uuid.UUID, NodeAggregate]:
    by_node: dict[uuid.UUID, list[EvidenceFact]] = defaultdict(list)
    for f in facts:
        if f.algorithm_version != SOURCE_EVIDENCE_ALGORITHM:
            continue
        by_node[f.curriculum_node_id].append(f)

    out: dict[uuid.UUID, NodeAggregate] = {}
    for node in nodes:
        rows = by_node.get(node.id, [])

        def _counts(etype: str, rows_local: list[EvidenceFact] = rows) -> tuple[Strength, int]:
            subset = [e for e in rows_local if e.evidence_type == etype]
            strong = sum(1 for e in subset if e.strength == "STRONG")
            weak = sum(1 for e in subset if e.strength == "WEAK")
            inconclusive = sum(1 for e in subset if e.strength == "INCONCLUSIVE")
            return aggregate_signal(strong, weak, inconclusive), weak

        concept, c_weak = _counts("CONCEPT")
        execution, e_weak = _counts("EXECUTION")
        procedure, p_weak = _counts("PROCEDURE")
        ratios = [Decimal(e.score_ratio) for e in rows]
        mean = (sum(ratios) / Decimal(len(ratios))) if ratios else None
        if mean is not None:
            mean = mean.quantize(Decimal("0.000001"))
        out[node.id] = NodeAggregate(
            node=node,
            concept=concept,
            execution=execution,
            procedure=procedure,
            evidence_count=len(rows),
            weak_evidence_count=c_weak + e_weak + p_weak,
            mean_score_ratio=mean,
            evidence_ids=tuple(sorted((e.id for e in rows), key=str)),
        )
    return out


def _target_kind_and_priority(
    agg: NodeAggregate,
) -> tuple[RecommendationKind, Literal[1, 2, 3]] | None:
    """Highest-priority direct remediation for a node with at least one WEAK signal."""
    if agg.concept == "WEAK":
        return "TARGET_CONCEPT", 1
    if agg.procedure == "WEAK":
        return "PROCEDURE_PRACTICE", 2
    # Concept is not WEAK here; execution-only weakness → practice, not relearn.
    if agg.execution == "WEAK":
        return "EXECUTION_PRACTICE", 3
    return None


def _default_rationale(kind: RecommendationKind, title: str) -> str:
    if kind == "TARGET_CONCEPT":
        return (
            f"Review {title} because current published evidence shows a concept gap."
        )
    if kind == "PROCEDURE_PRACTICE":
        return (
            f"Practice procedures for {title} because published evidence shows a "
            "procedure gap."
        )
    if kind == "EXECUTION_PRACTICE":
        return (
            f"Practice accurate execution for {title}; concept evidence is not weak, "
            "but execution evidence is."
        )
    return (
        f"Repair prerequisite {title} before the dependent target because published "
        "evidence shows a weakness."
    )


def _path_kind_for_recommendation(kind: RecommendationKind) -> PathStepKind:
    if kind == "PREREQUISITE_REPAIR":
        return "PREREQUISITE"
    if kind == "TARGET_CONCEPT":
        return "LEARN"
    if kind == "PROCEDURE_PRACTICE":
        return "GUIDED"
    return "INDEPENDENT"


def _order_required_prereq_nodes(
    target_id: uuid.UUID,
    *,
    edges_by_dependent: dict[uuid.UUID, list[PrerequisiteEdge]],
    required_edges: list[PrerequisiteEdge],
) -> list[uuid.UUID]:
    """Return REQUIRED prerequisite node IDs in dependency-first order."""
    ordered: list[uuid.UUID] = []
    seen: set[uuid.UUID] = set()
    required_pred_ids = {e.prerequisite_node_id for e in required_edges}

    def visit(nid: uuid.UUID) -> None:
        for edge in edges_by_dependent.get(nid, []):
            if edge.relationship_type != "REQUIRED":
                continue
            visit(edge.prerequisite_node_id)
        if nid != target_id and nid in required_pred_ids and nid not in seen:
            seen.add(nid)
            ordered.append(nid)

    visit(target_id)
    return ordered


def _detect_cycle(
    node_id: uuid.UUID,
    *,
    required_edges: dict[uuid.UUID, list[uuid.UUID]],
    visiting: set[uuid.UUID],
    visited: set[uuid.UUID],
) -> None:
    if node_id in visiting:
        raise LearningError(
            "CURRICULUM_PREREQUISITE_CYCLE",
            "Curriculum prerequisite graph contains a cycle",
        )
    if node_id in visited:
        return
    visiting.add(node_id)
    for pred in required_edges.get(node_id, []):
        _detect_cycle(
            pred, required_edges=required_edges, visiting=visiting, visited=visited
        )
    visiting.remove(node_id)
    visited.add(node_id)


def _transitive_prerequisites(
    target_id: uuid.UUID,
    *,
    edges_by_dependent: dict[uuid.UUID, list[PrerequisiteEdge]],
    relationship: RelationshipType,
) -> list[PrerequisiteEdge]:
    """BFS backward collecting unique edges of a given relationship type."""
    collected: list[PrerequisiteEdge] = []
    seen_edge_ids: set[uuid.UUID] = set()
    queue = [target_id]
    seen_nodes = {target_id}
    while queue:
        current = queue.pop(0)
        for edge in edges_by_dependent.get(current, []):
            if edge.relationship_type != relationship:
                continue
            if edge.id in seen_edge_ids:
                continue
            seen_edge_ids.add(edge.id)
            collected.append(edge)
            if edge.prerequisite_node_id not in seen_nodes:
                seen_nodes.add(edge.prerequisite_node_id)
                queue.append(edge.prerequisite_node_id)
    return collected


def build_learning_plan_structure(
    *,
    curriculum_id: uuid.UUID,
    nodes: list[NodeMeta],
    edges: list[PrerequisiteEdge],
    facts: list[EvidenceFact],
) -> LearningPlanStructure:
    """Compute server-authoritative recommendations and ordered path steps."""
    node_by_id = {n.id: n for n in nodes}
    eligible_facts = [
        f for f in facts if f.algorithm_version == SOURCE_EVIDENCE_ALGORITHM
    ]
    source_hash = compute_source_evidence_hash(eligible_facts)
    graph_hash = compute_curriculum_graph_hash(
        curriculum_id=curriculum_id, nodes=nodes, edges=edges
    )
    input_hash = compute_input_hash(
        source_evidence_hash=source_hash, curriculum_graph_hash=graph_hash
    )

    aggregates = aggregate_node_signals(nodes=nodes, facts=eligible_facts)

    # Index edges by dependent for backward traversal.
    edges_by_dependent: dict[uuid.UUID, list[PrerequisiteEdge]] = defaultdict(list)
    required_preds: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)
    for e in edges:
        if e.prerequisite_node_id not in node_by_id or e.dependent_node_id not in node_by_id:
            raise LearningError(
                "CURRICULUM_PREREQUISITE_INVALID",
                "Prerequisite edge references a node outside the selected curriculum",
            )
        edges_by_dependent[e.dependent_node_id].append(e)
        if e.relationship_type == "REQUIRED":
            required_preds[e.dependent_node_id].append(e.prerequisite_node_id)

    # Cycle detection over REQUIRED edges for all nodes that may be traversed.
    visited: set[uuid.UUID] = set()
    for nid in node_by_id:
        _detect_cycle(
            nid,
            required_edges=required_preds,
            visiting=set(),
            visited=visited,
        )

    # Direct weak targets.
    direct_targets: list[
        tuple[NodeAggregate, RecommendationKind, Literal[1, 2, 3]]
    ] = []
    for agg in aggregates.values():
        kind_pri = _target_kind_and_priority(agg)
        if kind_pri is None:
            continue
        kind, priority = kind_pri
        direct_targets.append((agg, kind, priority))

    recommendations: list[PlannedRecommendation] = []
    # Track PREREQUISITE_REPAIR / support keys to avoid duplicates across targets.
    repair_keys: set[tuple[uuid.UUID, str]] = set()

    for agg, kind, priority in direct_targets:
        node = agg.node
        prereq_links: list[PlannedPrerequisite] = []
        seq = 0

        required_edges = _transitive_prerequisites(
            node.id,
            edges_by_dependent=edges_by_dependent,
            relationship="REQUIRED",
        )
        required_nodes_ordered = _order_required_prereq_nodes(
            node.id,
            edges_by_dependent=edges_by_dependent,
            required_edges=required_edges,
        )

        for pred_id in required_nodes_ordered:
            pred_agg = aggregates.get(pred_id)
            pred_node = node_by_id[pred_id]
            if pred_agg is None:
                pred_agg = NodeAggregate(
                    node=pred_node,
                    concept="INCONCLUSIVE",
                    execution="INCONCLUSIVE",
                    procedure="INCONCLUSIVE",
                    evidence_count=0,
                    weak_evidence_count=0,
                    mean_score_ratio=None,
                    evidence_ids=(),
                )
            has_weak = (
                pred_agg.concept == "WEAK"
                or pred_agg.execution == "WEAK"
                or pred_agg.procedure == "WEAK"
            )
            has_strong = (
                pred_agg.concept == "STRONG"
                or pred_agg.execution == "STRONG"
                or pred_agg.procedure == "STRONG"
            )
            if has_weak:
                relevant: Strength = "WEAK"
            elif has_strong:
                relevant = "STRONG"
            else:
                relevant = "INCONCLUSIVE"

            seq += 1
            prereq_links.append(
                PlannedPrerequisite(
                    node_id=pred_id,
                    relationship_type="REQUIRED",
                    sequence=seq,
                )
            )

            if relevant == "WEAK":
                key = (pred_id, "PREREQUISITE_REPAIR")
                if key not in repair_keys:
                    repair_keys.add(key)
                    recommendations.append(
                        PlannedRecommendation(
                            target_node_id=pred_id,
                            recommendation_kind="PREREQUISITE_REPAIR",
                            priority=1,
                            rationale=_default_rationale(
                                "PREREQUISITE_REPAIR", pred_node.title
                            ),
                            concept_signal=pred_agg.concept,
                            execution_signal=pred_agg.execution,
                            procedure_signal=pred_agg.procedure,
                            evidence_count=pred_agg.evidence_count,
                            mean_evidence_score_ratio=pred_agg.mean_score_ratio,
                            evidence_ids=pred_agg.evidence_ids,
                            prerequisites=[],
                            target_node_code=pred_node.code,
                            target_node_title=pred_node.title,
                            target_node_type=pred_node.node_type,
                            sort_key=(
                                1,
                                -pred_agg.weak_evidence_count,
                                -pred_agg.evidence_count,
                                pred_node.code,
                                str(pred_id),
                                "PREREQUISITE_REPAIR",
                            ),
                        )
                    )
            # STRONG → omit repair; INCONCLUSIVE handled as MASTERY_CHECK in path

        # RECOMMENDED weak support (do not block target)
        recommended_edges = _transitive_prerequisites(
            node.id,
            edges_by_dependent=edges_by_dependent,
            relationship="RECOMMENDED",
        )
        for edge in sorted(
            recommended_edges, key=lambda e: (node_by_id[e.prerequisite_node_id].code, str(e.id))
        ):
            pred_id = edge.prerequisite_node_id
            pred_agg = aggregates.get(pred_id)
            pred_node = node_by_id[pred_id]
            if pred_agg is None:
                continue
            has_weak = (
                pred_agg.concept == "WEAK"
                or pred_agg.execution == "WEAK"
                or pred_agg.procedure == "WEAK"
            )
            if not has_weak:
                continue
            seq += 1
            prereq_links.append(
                PlannedPrerequisite(
                    node_id=pred_id,
                    relationship_type="RECOMMENDED",
                    sequence=seq,
                )
            )
            key = (pred_id, "PREREQUISITE_REPAIR_RECOMMENDED")
            if key not in repair_keys:
                repair_keys.add(key)
                recommendations.append(
                    PlannedRecommendation(
                        target_node_id=pred_id,
                        recommendation_kind="PREREQUISITE_REPAIR",
                        priority=2,
                        rationale=(
                            f"Optional support: review {pred_node.title} "
                            "(recommended prerequisite) before the target."
                        ),
                        concept_signal=pred_agg.concept,
                        execution_signal=pred_agg.execution,
                        procedure_signal=pred_agg.procedure,
                        evidence_count=pred_agg.evidence_count,
                        mean_evidence_score_ratio=pred_agg.mean_score_ratio,
                        evidence_ids=pred_agg.evidence_ids,
                        prerequisites=[],
                        target_node_code=pred_node.code,
                        target_node_title=pred_node.title,
                        target_node_type=pred_node.node_type,
                        sort_key=(
                            2,
                            -pred_agg.weak_evidence_count,
                            -pred_agg.evidence_count,
                            pred_node.code,
                            str(pred_id),
                            "PREREQUISITE_REPAIR",
                        ),
                    )
                )

        recommendations.append(
            PlannedRecommendation(
                target_node_id=node.id,
                recommendation_kind=kind,
                priority=priority,
                rationale=_default_rationale(kind, node.title),
                concept_signal=agg.concept,
                execution_signal=agg.execution,
                procedure_signal=agg.procedure,
                evidence_count=agg.evidence_count,
                mean_evidence_score_ratio=agg.mean_score_ratio,
                evidence_ids=agg.evidence_ids,
                prerequisites=prereq_links,
                target_node_code=node.code,
                target_node_title=node.title,
                target_node_type=node.node_type,
                sort_key=(
                    priority,
                    -agg.weak_evidence_count,
                    -agg.evidence_count,
                    node.code,
                    str(node.id),
                    kind,
                ),
            )
        )

    recommendations.sort(key=lambda r: r.sort_key)

    # Build ordered path: process dependents before their weak REQUIRED
    # prerequisites among direct targets so repair steps precede targets.
    path_steps: list[PlannedPathStep] = []
    path_seen: set[tuple[str, uuid.UUID, str]] = set()
    seq_no = 0

    weak_target_ids = {t[0].node.id for t in direct_targets}
    # Depth among weak targets: dependents get lower depth rank first.
    dependent_rank: dict[uuid.UUID, int] = {nid: 0 for nid in weak_target_ids}
    for e in edges:
        if e.relationship_type != "REQUIRED":
            continue
        if (
            e.prerequisite_node_id in weak_target_ids
            and e.dependent_node_id in weak_target_ids
        ):
            # Dependent should be processed before prerequisite → higher rank for prereq
            dependent_rank[e.prerequisite_node_id] = max(
                dependent_rank[e.prerequisite_node_id],
                dependent_rank.get(e.dependent_node_id, 0) + 1,
            )

    ordered_targets = sorted(
        direct_targets,
        key=lambda t: (
            dependent_rank.get(t[0].node.id, 0),
            t[2],
            -t[0].weak_evidence_count,
            -t[0].evidence_count,
            t[0].node.code,
            str(t[0].node.id),
        ),
    )

    for agg, kind, _priority in ordered_targets:
        node = agg.node
        # Already emitted as a prerequisite/check/target for a dependent.
        if any(entry[1] == node.id for entry in path_seen):
            continue

        required_edges = _transitive_prerequisites(
            node.id,
            edges_by_dependent=edges_by_dependent,
            relationship="REQUIRED",
        )
        required_nodes_ordered = _order_required_prereq_nodes(
            node.id,
            edges_by_dependent=edges_by_dependent,
            required_edges=required_edges,
        )

        for pred_id in required_nodes_ordered:
            pred_agg = aggregates.get(pred_id)
            pred_node = node_by_id[pred_id]
            if pred_agg is None:
                has_weak = False
                has_strong = False
            else:
                has_weak = (
                    pred_agg.concept == "WEAK"
                    or pred_agg.execution == "WEAK"
                    or pred_agg.procedure == "WEAK"
                )
                has_strong = (
                    pred_agg.concept == "STRONG"
                    or pred_agg.execution == "STRONG"
                    or pred_agg.procedure == "STRONG"
                )
            if has_weak:
                dedupe = ("PREREQUISITE", pred_id, "REQUIRED")
                if dedupe not in path_seen:
                    path_seen.add(dedupe)
                    seq_no += 1
                    path_steps.append(
                        PlannedPathStep(
                            curriculum_node_id=pred_id,
                            kind="PREREQUISITE",
                            sequence=seq_no,
                            title=f"Required prerequisite repair — {pred_node.title}",
                            description=_default_rationale(
                                "PREREQUISITE_REPAIR", pred_node.title
                            ),
                            evidence_basis="WEAK",
                            relationship_type="REQUIRED",
                            recommendation_key=(
                                1,
                                str(pred_id),
                                "PREREQUISITE_REPAIR",
                            ),
                        )
                    )
            elif not has_strong:
                # INCONCLUSIVE / no evidence → mastery check
                dedupe = ("MASTERY_CHECK", pred_id, "REQUIRED")
                if dedupe not in path_seen:
                    path_seen.add(dedupe)
                    seq_no += 1
                    path_steps.append(
                        PlannedPathStep(
                            curriculum_node_id=pred_id,
                            kind="MASTERY_CHECK",
                            sequence=seq_no,
                            title=f"Prerequisite check — {pred_node.title}",
                            description=(
                                f"Confirm mastery of {pred_node.title} before "
                                f"continuing to {node.title}."
                            ),
                            evidence_basis="INCONCLUSIVE",
                            relationship_type="REQUIRED",
                            recommendation_key=None,
                        )
                    )
            # STRONG → omit

        # Recommended weak support steps (after required, before target)
        recommended_edges = _transitive_prerequisites(
            node.id,
            edges_by_dependent=edges_by_dependent,
            relationship="RECOMMENDED",
        )
        for edge in sorted(
            recommended_edges,
            key=lambda e: (node_by_id[e.prerequisite_node_id].code, str(e.id)),
        ):
            pred_id = edge.prerequisite_node_id
            pred_agg = aggregates.get(pred_id)
            pred_node = node_by_id[pred_id]
            if pred_agg is None:
                continue
            has_weak = (
                pred_agg.concept == "WEAK"
                or pred_agg.execution == "WEAK"
                or pred_agg.procedure == "WEAK"
            )
            if not has_weak:
                continue
            dedupe = ("PREREQUISITE", pred_id, "RECOMMENDED")
            if dedupe in path_seen:
                continue
            path_seen.add(dedupe)
            seq_no += 1
            path_steps.append(
                PlannedPathStep(
                    curriculum_node_id=pred_id,
                    kind="PREREQUISITE",
                    sequence=seq_no,
                    title=f"Recommended prerequisite — {pred_node.title}",
                    description=(
                        f"Optional support on {pred_node.title} before {node.title}."
                    ),
                    evidence_basis="WEAK",
                    relationship_type="RECOMMENDED",
                    recommendation_key=(
                        2,
                        str(pred_id),
                        "PREREQUISITE_REPAIR",
                    ),
                )
            )

        path_kind = _path_kind_for_recommendation(kind)
        dedupe = (path_kind, node.id, kind)
        if dedupe not in path_seen:
            path_seen.add(dedupe)
            seq_no += 1
            label = {
                "TARGET_CONCEPT": "Target concept",
                "PROCEDURE_PRACTICE": "Procedure practice",
                "EXECUTION_PRACTICE": "Execution practice",
            }[kind]
            path_steps.append(
                PlannedPathStep(
                    curriculum_node_id=node.id,
                    kind=path_kind,
                    sequence=seq_no,
                    title=f"{label} — {node.title}",
                    description=_default_rationale(kind, node.title),
                    evidence_basis="WEAK",
                    relationship_type=None,
                    recommendation_key=(
                        _priority,
                        str(node.id),
                        kind,
                    ),
                )
            )

    no_gap = None
    if not recommendations:
        no_gap = (
            "No evidence-backed learning gaps were identified from currently "
            "published results."
        )

    return LearningPlanStructure(
        source_evidence_hash=source_hash,
        curriculum_graph_hash=graph_hash,
        input_hash=input_hash,
        recommendations=recommendations,
        path_steps=path_steps,
        no_gap_message=no_gap,
    )


def contains_url_like(text: str | None) -> bool:
    if not text:
        return False
    lowered = text.lower()
    return "http://" in lowered or "https://" in lowered or "www." in lowered


def reject_provider_urls(*texts: str | None) -> None:
    for t in texts:
        if contains_url_like(t):
            raise LearningError(
                "LEARNING_PROVIDER_URL_REJECTED",
                "Provider output must not contain URLs",
            )

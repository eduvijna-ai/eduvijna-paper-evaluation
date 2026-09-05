import uuid
from collections import defaultdict
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import CurriculumNode, CurriculumPrerequisite


def build_tree(nodes: list[CurriculumNode]) -> list[dict[str, Any]]:
    """Build an ordered forest without requiring ORM relationships."""
    children: dict[uuid.UUID | None, list[CurriculumNode]] = defaultdict(list)
    for node in nodes:
        children[node.parent_id].append(node)
    for group in children.values():
        group.sort(key=lambda node: (node.sequence, node.code))

    def serialize(node: CurriculumNode) -> dict[str, Any]:
        return {
            "id": node.id,
            "curriculum_id": node.curriculum_id,
            "parent_id": node.parent_id,
            "node_type": node.node_type,
            "code": node.code,
            "name": node.name,
            "description": node.description,
            "sequence": node.sequence,
            "metadata": node.metadata_json,
            "status": node.status,
            "children": [serialize(child) for child in children[node.id]],
        }

    return [serialize(root) for root in children[None]]


async def ensure_parent_acyclic(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    node_id: uuid.UUID | None,
    parent_id: uuid.UUID | None,
) -> None:
    if parent_id is None:
        return
    if parent_id == node_id:
        raise HTTPException(409, "A curriculum node cannot parent itself")
    current: uuid.UUID | None = parent_id
    seen: set[uuid.UUID] = set()
    while current is not None:
        if current == node_id or current in seen:
            raise HTTPException(409, "Curriculum parent cycle detected")
        seen.add(current)
        parent = await db.scalar(
            select(CurriculumNode).where(
                CurriculumNode.id == current, CurriculumNode.tenant_id == tenant_id
            )
        )
        if parent is None:
            raise HTTPException(404, "Parent curriculum node not found")
        current = parent.parent_id


async def ensure_prerequisite_acyclic(
    db: AsyncSession,
    *,
    tenant_id: uuid.UUID,
    curriculum_id: uuid.UUID,
    prerequisite_id: uuid.UUID,
    dependent_id: uuid.UUID,
) -> None:
    if prerequisite_id == dependent_id:
        raise HTTPException(409, "A node cannot be its own prerequisite")
    edges = (
        await db.execute(
            select(
                CurriculumPrerequisite.prerequisite_node_id,
                CurriculumPrerequisite.dependent_node_id,
            ).where(
                CurriculumPrerequisite.tenant_id == tenant_id,
                CurriculumPrerequisite.curriculum_id == curriculum_id,
            )
        )
    ).all()
    graph: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)
    for source, target in edges:
        graph[source].append(target)
    graph[prerequisite_id].append(dependent_id)

    visiting: set[uuid.UUID] = set()
    visited: set[uuid.UUID] = set()

    def dfs(node: uuid.UUID) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        if any(dfs(child) for child in graph[node]):
            return True
        visiting.remove(node)
        visited.add(node)
        return False

    if any(dfs(node) for node in list(graph)):
        raise HTTPException(409, "Curriculum prerequisite cycle detected")

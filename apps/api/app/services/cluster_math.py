"""Deterministic cosine-graph clustering helpers (COSINE_GRAPH_V1)."""

from __future__ import annotations

import math
from collections.abc import Sequence


def l2_normalize(vector: Sequence[float]) -> list[float]:
    """Return an L2-normalized copy. Zero vectors stay zero."""
    squares = sum(float(v) * float(v) for v in vector)
    if squares <= 0.0:
        return [0.0 for _ in vector]
    norm = math.sqrt(squares)
    return [float(v) / norm for v in vector]


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity for equal-length vectors (prefer pre-normalized)."""
    if len(a) != len(b):
        raise ValueError("cosine_similarity requires equal-length vectors")
    if not a:
        return 0.0
    # If either is zero-vector, similarity is 0.
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b, strict=True):
        fx = float(x)
        fy = float(y)
        dot += fx * fy
        na += fx * fx
        nb += fy * fy
    if na <= 0.0 or nb <= 0.0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


def connected_components(
    ids: Sequence[str],
    embeddings: Sequence[Sequence[float]],
    *,
    threshold: float,
) -> list[list[str]]:
    """Deterministic connected components on an undirected cosine-similarity graph.

    Edge exists when cosine_similarity(i, j) >= threshold.
    Components are sorted by their lexicographically smallest member id.
    Members within each component are sorted lexicographically.
    Input order does not affect the result.
    """
    if len(ids) != len(embeddings):
        raise ValueError("ids and embeddings must have the same length")
    if not ids:
        return []

    # Stable order by id for adjacency construction.
    order = sorted(range(len(ids)), key=lambda i: ids[i])
    ordered_ids = [ids[i] for i in order]
    ordered_emb = [l2_normalize(embeddings[i]) for i in order]
    n = len(ordered_ids)

    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra == rb:
            return
        # Deterministic union by smaller root index.
        if ra < rb:
            parent[rb] = ra
        else:
            parent[ra] = rb

    for i in range(n):
        for j in range(i + 1, n):
            if cosine_similarity(ordered_emb[i], ordered_emb[j]) >= threshold:
                union(i, j)

    buckets: dict[int, list[str]] = {}
    for i, member_id in enumerate(ordered_ids):
        root = find(i)
        buckets.setdefault(root, []).append(member_id)

    components: list[list[str]] = []
    for members in buckets.values():
        components.append(sorted(members))
    components.sort(key=lambda c: c[0])
    return components

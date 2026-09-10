"""Deterministic fixed embedding provider for B18 clustering (CI / non-prod)."""

from __future__ import annotations

import hashlib
import math
import re

from app.ai.types import EmbeddingInput, EmbeddingResult

_TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)
FIXED_EMBED_DIM = 32


def _bag_of_hash_embedding(text: str, *, dim: int = FIXED_EMBED_DIM) -> list[float]:
    """Hash bag-of-tokens into a fixed-dim L2-normalized vector."""
    vec = [0.0] * dim
    tokens = _TOKEN_RE.findall((text or "").lower())
    if not tokens:
        # Deterministic non-zero tiny vector for empty text so cosine is defined.
        digest = hashlib.sha256(b"").digest()
        for i in range(dim):
            vec[i] = ((digest[i % len(digest)] / 255.0) * 2.0) - 1.0
    else:
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            for i in range(dim):
                # Map byte to [-1, 1] contribution.
                vec[i] += ((digest[i % len(digest)] / 255.0) * 2.0) - 1.0
    norm = math.sqrt(sum(v * v for v in vec))
    if norm <= 0.0:
        return [0.0] * dim
    return [v / norm for v in vec]


class FixedEmbeddingProvider:
    """Credential-free deterministic embeddings for CI and local tests."""

    provider_name = "fixed"
    model = "fixed-embed-v1"
    model_version = "1"
    embedding_dim = FIXED_EMBED_DIM

    def __init__(self, *, allow_non_test: bool = False) -> None:
        self._allow_non_test = allow_non_test

    async def embed_texts(self, request: EmbeddingInput) -> EmbeddingResult:
        vectors = [_bag_of_hash_embedding(text, dim=self.embedding_dim) for text in request.texts]
        return EmbeddingResult(
            vectors=vectors,
            provider=self.provider_name,
            model=self.model,
            model_version=self.model_version,
            embedding_dim=self.embedding_dim,
        )


class FixedEmbeddingProviderAlt:
    """Deterministic alternate fixed provider for B18.1 reproducibility tests."""

    provider_name = "fixed"
    model = "fixed-embed-v1-alt"
    model_version = "2"
    embedding_dim = FIXED_EMBED_DIM

    def __init__(
        self,
        *,
        provider_name: str | None = None,
        model: str | None = None,
        model_version: str | None = None,
        embedding_dim: int | None = None,
        allow_non_test: bool = False,
    ) -> None:
        if provider_name is not None:
            self.provider_name = provider_name
        if model is not None:
            self.model = model
        if model_version is not None:
            self.model_version = model_version
        if embedding_dim is not None:
            self.embedding_dim = embedding_dim
        self._allow_non_test = allow_non_test

    async def embed_texts(self, request: EmbeddingInput) -> EmbeddingResult:
        # Same hashing algorithm; identity differs via provider/model/version metadata.
        vectors = [_bag_of_hash_embedding(text, dim=self.embedding_dim) for text in request.texts]
        return EmbeddingResult(
            vectors=vectors,
            provider=self.provider_name,
            model=self.model,
            model_version=self.model_version,
            embedding_dim=self.embedding_dim,
        )


class NoneEmbeddingProvider:
    """Explicit unavailable embedding provider."""

    provider_name = "none"
    model = "none"
    model_version = "0"
    embedding_dim = 0

    async def embed_texts(self, request: EmbeddingInput) -> EmbeddingResult:
        raise RuntimeError("Embedding provider is not configured (AI_PROVIDER_TEXT=none)")

"""
Semantic retrieval primitives for MaxxAgentFramework RAG.

This module provides:
- Embedder protocol
- Simple deterministic local embedder (no external dependencies)
- In-memory vector store
- Retriever with cosine similarity

Notes:
- The default embedder is intentionally simple/deterministic so examples run
  without external services. Swap with an API embedder later.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from maxxa_agent.rag.loader import DocumentChunk


class Embedder(Protocol):
    """Embeds text into a vector space."""

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Return one embedding vector per input text."""


@dataclass(frozen=True, slots=True)
class LocalHashEmbedder:
    """
    Deterministic embedder based on hashing token n-grams.

    This is not SOTA, but it is:
    - fast
    - dependency-free
    - stable across runs
    - good enough to demonstrate retrieval wiring
    """

    dim: int = 256

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if self.dim <= 0:
            raise ValueError("dim must be > 0")
        return [_embed_one(t, self.dim) for t in texts]


@dataclass(slots=True)
class VectorRecord:
    chunk: DocumentChunk
    embedding: list[float]


class InMemoryVectorStore:
    """Stores embeddings for chunks and supports similarity search."""

    def __init__(self) -> None:
        self._records: list[VectorRecord] = []

    def add(self, chunk: DocumentChunk, embedding: list[float]) -> None:
        self._records.append(VectorRecord(chunk=chunk, embedding=embedding))

    def extend(self, chunks: Sequence[DocumentChunk], embeddings: Sequence[list[float]]) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings must have same length")
        for c, e in zip(chunks, embeddings, strict=True):
            self.add(c, e)

    def search(self, query_embedding: list[float], *, top_k: int = 5) -> list[tuple[float, DocumentChunk]]:
        scored: list[tuple[float, DocumentChunk]] = []
        for r in self._records:
            scored.append((_cosine(query_embedding, r.embedding), r.chunk))
        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[:top_k]


class Retriever:
    """High-level semantic retriever (embed + vector search)."""

    def __init__(
        self,
        *,
        embedder: Embedder,
        store: InMemoryVectorStore | None = None,
    ) -> None:
        self.embedder = embedder
        self.store = store or InMemoryVectorStore()

    def add_chunks(self, chunks: Sequence[DocumentChunk]) -> None:
        embeddings = self.embedder.embed([c.text for c in chunks])
        self.store.extend(chunks, embeddings)

    def query(self, query: str, *, top_k: int = 5) -> list[Mapping[str, Any]]:
        q_emb = self.embedder.embed([query])[0]
        hits = self.store.search(q_emb, top_k=top_k)
        out: list[Mapping[str, Any]] = []
        for score, chunk in hits:
            out.append(
                {
                    "score": float(score),
                    "chunk_id": chunk.chunk_id,
                    "source": chunk.source,
                    "text": chunk.text,
                    "metadata": dict(chunk.metadata),
                }
            )
        return out


_TOKEN_RE = re.compile(r"[a-zA-Z0-9_]+")


def _embed_one(text: str, dim: int) -> list[float]:
    vec = [0.0] * dim
    toks = [t.lower() for t in _TOKEN_RE.findall(text)]
    if not toks:
        return vec
    # hashed unigrams + bigrams
    for i, t in enumerate(toks):
        h = hash(("u", t)) % dim
        vec[h] += 1.0
        if i + 1 < len(toks):
            b = (t, toks[i + 1])
            hb = hash(("b", b)) % dim
            vec[hb] += 1.0
    # L2 normalize
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    if len(a) != len(b):
        raise ValueError("vector dims mismatch")
    return float(sum(x * y for x, y in zip(a, b, strict=True)))


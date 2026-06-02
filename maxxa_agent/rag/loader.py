"""
Document loading and chunking utilities (LlamaIndex-style building blocks).

Components:
- DocumentLoader: load documents from files and URLs (extensible for DBs)
- TextSplitter: chunk documents into overlap-aware segments

This module is dependency-light and safe-by-default (bounded reads, encoding handling).
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Iterable, Mapping, Optional

import httpx


@dataclass(frozen=True, slots=True)
class Document:
    """A loaded document with optional metadata."""

    text: str
    source: str
    metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class DocumentChunk:
    """A chunk of a document."""

    text: str
    source: str
    chunk_id: str
    metadata: Mapping[str, object] = field(default_factory=dict)


class DocumentLoader:
    """Load documents from multiple sources."""

    def __init__(self, *, max_chars: int = 2_000_000) -> None:
        if max_chars <= 0:
            raise ValueError("max_chars must be > 0")
        self.max_chars = max_chars

    def load_text_file(self, path: str, *, encoding: str = "utf-8") -> Document:
        with open(path, "r", encoding=encoding, errors="replace") as f:
            text = f.read(self.max_chars + 1)
        if len(text) > self.max_chars:
            text = text[: self.max_chars - 1] + "…"
        return Document(text=text, source=os.path.abspath(path))

    def load_url(self, url: str, *, timeout_s: float = 20.0) -> Document:
        with httpx.Client(timeout=timeout_s, follow_redirects=True) as client:
            resp = client.get(url)
            resp.raise_for_status()
            text = resp.text
        if len(text) > self.max_chars:
            text = text[: self.max_chars - 1] + "…"
        return Document(text=text, source=url)


class TextSplitter:
    """
    Chunk documents into overlapping segments.

    This splitter favors "semantic-ish" boundaries (blank lines / sentences),
    while enforcing a hard maximum chunk size.
    """

    def __init__(self, *, chunk_size: int = 800, chunk_overlap: int = 100) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be > 0")
        if chunk_overlap < 0 or chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be >=0 and < chunk_size")
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split(self, doc: Document, *, prefix_id: Optional[str] = None) -> list[DocumentChunk]:
        normalized = _normalize_text(doc.text)
        units = _split_units(normalized)

        chunks: list[str] = []
        buf: list[str] = []
        buf_len = 0

        def flush() -> None:
            nonlocal buf, buf_len
            if not buf:
                return
            chunk = "".join(buf).strip()
            if chunk:
                chunks.append(chunk)
            buf = []
            buf_len = 0

        for u in units:
            if buf_len + len(u) > self.chunk_size and buf:
                flush()
                # overlap: carry last N chars from previous chunk
                if self.chunk_overlap > 0 and chunks:
                    overlap = chunks[-1][-self.chunk_overlap :]
                    buf = [overlap]
                    buf_len = len(overlap)
            buf.append(u)
            buf_len += len(u)

        flush()

        out: list[DocumentChunk] = []
        pid = prefix_id or re.sub(r"[^a-zA-Z0-9]+", "_", doc.source)[-40:]
        for i, c in enumerate(chunks):
            out.append(
                DocumentChunk(
                    text=c,
                    source=doc.source,
                    chunk_id=f"{pid}:{i}",
                    metadata=dict(doc.metadata),
                )
            )
        return out


_WHITESPACE_RE = re.compile(r"[ \t]+")


def _normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _WHITESPACE_RE.sub(" ", text)
    return text.strip()


def _split_units(text: str) -> list[str]:
    """
    Split into roughly sentence/paragraph sized units.
    Keeps separators so reconstruction is stable.
    """
    if not text:
        return []
    # First split by blank lines
    paras = re.split(r"(\n\s*\n)", text)
    units: list[str] = []
    for p in paras:
        if not p:
            continue
        if p.strip() == "":
            units.append("\n\n")
            continue
        # Then split into sentences-ish
        sentences = re.split(r"(?<=[.!?])\s+", p)
        for s in sentences:
            if s:
                units.append(s + " ")
    return units


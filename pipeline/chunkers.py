"""Chunking strategies. Each chunker turns one Document into a list of Chunks.

- fixed:          sliding token window, ignores document structure
- heading_aware:  one chunk per Markdown section, with a heading breadcrumb
- semantic:       splits where consecutive sentences stop being similar (embedding distance)
"""

import re
from typing import List, Optional, Protocol, Tuple

import numpy as np

from pipeline.corpus import Chunk, Document, _encoder, count_tokens
from pipeline.embeddings import Embedder

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z`*(\[])")


class Chunker(Protocol):
    def split(self, doc: Document) -> List[Chunk]: ...


def _to_chunks(doc: Document, pieces: List[Tuple[str, str]]) -> List[Chunk]:
    """pieces: (section breadcrumb, text) pairs, in document order."""
    return [
        Chunk(
            chunk_id=f"{doc.doc_id}::{i:03d}",
            doc_id=doc.doc_id,
            title=doc.title,
            source_url=doc.source_url,
            doc_type=doc.doc_type,
            text=text.strip(),
            section=section,
        )
        for i, (section, text) in enumerate(pieces)
        if text.strip()
    ]


def _token_windows(text: str, size: int, overlap: int) -> List[str]:
    tokens = _encoder().encode(text)
    if len(tokens) <= size:
        return [text]
    windows, start = [], 0
    while start < len(tokens):
        windows.append(_encoder().decode(tokens[start:start + size]))
        if start + size >= len(tokens):
            break
        start += size - overlap
    return windows


class FixedTokenChunker:
    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split(self, doc: Document) -> List[Chunk]:
        return _to_chunks(doc, [("", w) for w in _token_windows(doc.text, self.chunk_size, self.chunk_overlap)])


class HeadingAwareChunker:
    def __init__(self, max_tokens: int = 400, min_tokens: int = 40):
        self.max_tokens = max_tokens
        self.min_tokens = min_tokens

    def _sections(self, text: str) -> List[Tuple[str, str]]:
        """Splits on Markdown headings (outside code fences) into (breadcrumb, body) pairs."""
        stack: List[Tuple[int, str]] = []
        sections, body, in_fence = [], [], False

        def flush():
            sections.append((" > ".join(h for _, h in stack), "\n".join(body)))
            body.clear()

        for line in text.splitlines():
            if line.strip().startswith("```"):
                in_fence = not in_fence
            m = None if in_fence else HEADING_RE.match(line)
            if m:
                flush()
                level = len(m.group(1))
                stack = [(lvl, h) for lvl, h in stack if lvl < level] + [(level, m.group(2).strip())]
            else:
                body.append(line)
        flush()
        return [(crumb, b) for crumb, b in sections if b.strip()]

    def _pack_paragraphs(self, body: str) -> List[str]:
        """Splits an oversized section on blank lines, packing paragraphs up to max_tokens."""
        parts, current = [], ""
        for para in re.split(r"\n\s*\n", body):
            candidate = f"{current}\n\n{para}" if current else para
            if count_tokens(candidate) <= self.max_tokens:
                current = candidate
                continue
            if current:
                parts.append(current)
            if count_tokens(para) > self.max_tokens:
                parts.extend(_token_windows(para, self.max_tokens, 0))
                current = ""
            else:
                current = para
        if current:
            parts.append(current)
        return parts

    def split(self, doc: Document) -> List[Chunk]:
        pieces: List[Tuple[str, str]] = []
        for crumb, body in self._sections(doc.text):
            # Docs open with "# <title>"; the title is already in every chunk's embed_text.
            crumb = crumb.removeprefix(doc.title).removeprefix(" > ")
            # Fold tiny sections into the previous chunk rather than emitting near-empty chunks.
            if pieces and count_tokens(body) < self.min_tokens:
                prev_crumb, prev_text = pieces[-1]
                merged = f"{prev_text}\n\n{crumb.split(' > ')[-1]}\n{body}"
                if count_tokens(merged) <= self.max_tokens:
                    pieces[-1] = (prev_crumb, merged)
                    continue
            pieces.extend((crumb, part) for part in self._pack_paragraphs(body))
        return _to_chunks(doc, pieces)


class SemanticChunker:
    def __init__(self, embedder: Embedder, breakpoint_percentile: float = 90,
                 max_tokens: int = 400, min_tokens: int = 40):
        self.embedder = embedder
        self.breakpoint_percentile = breakpoint_percentile
        self.max_tokens = max_tokens
        self.min_tokens = min_tokens

    @staticmethod
    def _units(text: str) -> List[Tuple[str, bool]]:
        """Sentence-level units as (text, is_heading). Markdown lines are never merged across."""
        units = []
        for line in text.splitlines():
            if not line.strip():
                continue
            if HEADING_RE.match(line):
                units.append((line, True))
            else:
                units.extend((s, False) for s in SENTENCE_RE.split(line) if s.strip())
        return units

    def split(self, doc: Document) -> List[Chunk]:
        units = self._units(doc.text)
        if len(units) < 2:
            return _to_chunks(doc, [("", doc.text)])

        vectors = self.embedder.embed([u for u, _ in units])
        distances = 1.0 - np.sum(vectors[:-1] * vectors[1:], axis=1)
        threshold = float(np.percentile(distances, self.breakpoint_percentile))

        pieces, current = [], [units[0][0]]
        for i in range(1, len(units)):
            text, _ = units[i]
            prev_is_heading = units[i - 1][1]
            current_tokens = count_tokens("\n".join(current))
            topic_shift = distances[i - 1] > threshold and current_tokens >= self.min_tokens
            too_big = current_tokens + count_tokens(text) > self.max_tokens
            # Never leave a heading dangling at the end of a chunk.
            if (topic_shift or too_big) and not prev_is_heading:
                pieces.append(("", "\n".join(current)))
                current = []
            current.append(text)
        pieces.append(("", "\n".join(current)))
        return _to_chunks(doc, pieces)


def build_chunker(chunker_type: str, params: dict, embedder: Optional[Embedder] = None) -> Chunker:
    if chunker_type == "fixed":
        return FixedTokenChunker(**params)
    if chunker_type == "heading_aware":
        return HeadingAwareChunker(**params)
    if chunker_type == "semantic":
        if embedder is None:
            raise ValueError("semantic chunker needs an embedder")
        return SemanticChunker(embedder, **params)
    raise ValueError(f"unknown chunker type: {chunker_type}")

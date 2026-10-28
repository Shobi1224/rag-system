"""Retrievers: dense vector, BM25 keyword, and hybrid (Reciprocal Rank Fusion of both)."""

import re
from typing import Dict, List, Optional, Protocol, Tuple

import numpy as np
from rank_bm25 import BM25Okapi

from pipeline.corpus import Chunk
from pipeline.index import VectorIndex

# Keeps config keys like "min.insync.replicas" and "KIP-848" as single tokens.
TOKEN_RE = re.compile(r"[a-z0-9]+(?:[._-][a-z0-9]+)*")

Hits = List[Tuple[Chunk, float]]


class Retriever(Protocol):
    def search(self, query: str, k: int) -> Hits: ...


def tokenize(text: str) -> List[str]:
    tokens = TOKEN_RE.findall(text.lower())
    # Also index the parts of compound tokens, so "insync" matches "min.insync.replicas".
    parts = [p for t in tokens if re.search(r"[._-]", t) for p in re.split(r"[._-]", t)]
    return tokens + parts


class VectorRetriever:
    def __init__(self, index: VectorIndex):
        self.index = index

    def search(self, query: str, k: int) -> Hits:
        return self.index.search(query, k)


class BM25Retriever:
    def __init__(self, chunks: List[Chunk]):
        self.chunks = chunks
        self.bm25 = BM25Okapi([tokenize(c.embed_text) for c in chunks])

    def search(self, query: str, k: int) -> Hits:
        scores = self.bm25.get_scores(tokenize(query))
        top = np.argsort(scores)[::-1][:k]
        return [(self.chunks[i], float(scores[i])) for i in top]


class HybridRetriever:
    def __init__(self, vector: VectorRetriever, bm25: BM25Retriever, candidates: int = 20, rrf_k: int = 60):
        self.vector = vector
        self.bm25 = bm25
        self.candidates = candidates
        self.rrf_k = rrf_k

    def search(self, query: str, k: int) -> Hits:
        scores: Dict[str, float] = {}
        by_id: Dict[str, Chunk] = {}
        for hits in (self.vector.search(query, self.candidates), self.bm25.search(query, self.candidates)):
            for rank, (chunk, _) in enumerate(hits):
                by_id[chunk.chunk_id] = chunk
                scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0.0) + 1.0 / (self.rrf_k + rank + 1)
        ranked = sorted(scores, key=scores.get, reverse=True)[:k]
        return [(by_id[cid], scores[cid]) for cid in ranked]


def build_retriever(retriever_type: str, params: dict, chunks: List[Chunk],
                    index: Optional[VectorIndex]) -> Retriever:
    if retriever_type == "vector":
        return VectorRetriever(index)
    if retriever_type == "bm25":
        return BM25Retriever(chunks)
    if retriever_type == "hybrid":
        return HybridRetriever(VectorRetriever(index), BM25Retriever(chunks), **params)
    raise ValueError(f"unknown retriever type: {retriever_type}")

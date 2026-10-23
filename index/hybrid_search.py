"""Hybrid Search (BM25 + Vector RRF) and Cross-Encoder Reranker."""

from typing import List, Dict, Any, Optional
import numpy as np


class BM25Searcher:
    """BM25 keyword search indexer."""
    def __init__(self, corpus: List[Dict[str, Any]]):
        self.corpus = corpus
        self.tokenized_corpus = [doc["text"].lower().split() for doc in corpus]
        try:
            from rank_bm25 import BM25Okapi
            self.bm25 = BM25Okapi(self.tokenized_corpus)
        except ImportError:
            self.bm25 = None

    def search(self, query: str, top_k: int = 10) -> List[Dict[str, Any]]:
        if not self.bm25:
            return self.corpus[:top_k]
        tokenized_query = query.lower().split()
        scores = self.bm25.get_scores(tokenized_query)
        top_indices = np.argsort(scores)[::-1][:top_k]
        
        results = []
        for idx in top_indices:
            doc = dict(self.corpus[idx])
            doc["bm25_score"] = float(scores[idx])
            results.append(doc)
        return results


def reciprocal_rank_fusion(
    vector_results: List[Dict[str, Any]],
    bm25_results: List[Dict[str, Any]],
    k: int = 60,
    top_n: int = 5
) -> List[Dict[str, Any]]:
    """Merges vector search and BM25 search rankings using Reciprocal Rank Fusion (RRF)."""
    scores: Dict[str, float] = {}
    doc_map: Dict[str, Dict[str, Any]] = {}

    for rank, doc in enumerate(vector_results):
        doc_id = str(doc.get("id") or doc.get("text", "")[:30])
        doc_map[doc_id] = doc
        scores[doc_id] = scores.get(doc_id, 0.0) + (1.0 / (k + rank + 1))

    for rank, doc in enumerate(bm25_results):
        doc_id = str(doc.get("id") or doc.get("text", "")[:30])
        doc_map[doc_id] = doc
        scores[doc_id] = scores.get(doc_id, 0.0) + (1.0 / (k + rank + 1))

    # Sort documents by accumulated RRF score
    sorted_doc_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)[:top_n]
    fused_results = []
    for d_id in sorted_doc_ids:
        item = dict(doc_map[d_id])
        item["rrf_score"] = scores[d_id]
        fused_results.append(item)

    return fused_results


class CrossEncoderReranker:
    """Reranks retrieved candidates using a Cross-Encoder model."""
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.model_name = model_name
        self.model = None

    def load_model(self):
        if self.model is None:
            try:
                from sentence_transformers import CrossEncoder
                self.model = CrossEncoder(self.model_name)
            except Exception as e:
                print(f"Warning: could not load CrossEncoder ({e})")

    def rerank(self, query: str, candidates: List[Dict[str, Any]], top_k: int = 5) -> List[Dict[str, Any]]:
        self.load_model()
        if not self.model or not candidates:
            return candidates[:top_k]

        pairs = [[query, c.get("text", "")] for c in candidates]
        scores = self.model.predict(pairs)

        for i, score in enumerate(scores):
            candidates[i]["rerank_score"] = float(score)

        reranked = sorted(candidates, key=lambda x: x.get("rerank_score", 0.0), reverse=True)
        return reranked[:top_k]

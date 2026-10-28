"""RAGPipeline: builds chunker -> index -> retriever from a PipelineConfig, with LangSmith tracing."""

import statistics
from typing import Any, Dict, List

from langsmith import traceable

from pipeline.chunkers import build_chunker
from pipeline.corpus import Chunk, load_corpus
from pipeline.embeddings import get_embedder
from pipeline.index import VectorIndex
from pipeline.retrievers import build_retriever
from pipeline.settings import PipelineConfig


def _as_document(chunk: Chunk, score: float) -> Dict[str, Any]:
    """LangSmith renders retriever outputs in this shape as a readable list of documents."""
    return {
        "type": "Document",
        "page_content": chunk.text,
        "metadata": {
            "chunk_id": chunk.chunk_id,
            "doc_id": chunk.doc_id,
            "title": chunk.title,
            "section": chunk.section,
            "source_url": chunk.source_url,
            "tokens": chunk.tokens,
            "score": round(score, 4),
        },
    }


class RAGPipeline:
    def __init__(self, cfg: PipelineConfig):
        self.cfg = cfg
        embedder = get_embedder(cfg.embedding_model)
        chunker = build_chunker(cfg.chunker.type, cfg.chunker.params, embedder)
        self.chunks: List[Chunk] = [c for doc in load_corpus() for c in chunker.split(doc)]

        index = None
        if cfg.retriever.type in ("vector", "hybrid"):
            index = VectorIndex(self.chunks, embedder, collection=f"kafka_{cfg.index_key()}")
        self.retriever = build_retriever(cfg.retriever.type, cfg.retriever.params, self.chunks, index)

        self.retrieve = traceable(run_type="retriever", name=f"retrieve:{cfg.retriever.type}")(self._retrieve)
        self.run = traceable(run_type="chain", name=cfg.name, metadata=cfg.as_metadata())(self._run)

    def stats(self) -> Dict[str, Any]:
        tokens = [c.tokens for c in self.chunks]
        return {
            "num_chunks": len(self.chunks),
            "avg_chunk_tokens": round(statistics.mean(tokens), 1),
            "max_chunk_tokens": max(tokens),
        }

    def _retrieve(self, question: str) -> List[Dict[str, Any]]:
        return [_as_document(c, s) for c, s in self.retriever.search(question, self.cfg.top_k)]

    def _run(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        documents = self.retrieve(inputs["question"])
        return {
            "documents": documents,
            "doc_ids": [d["metadata"]["doc_id"] for d in documents],
            "context_tokens": sum(d["metadata"]["tokens"] for d in documents),
        }

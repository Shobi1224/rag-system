"""Qdrant vector index. Uses the Qdrant server when reachable, otherwise embedded local storage."""

from functools import lru_cache
from typing import List, Tuple

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

import config
from pipeline.corpus import Chunk
from pipeline.embeddings import Embedder

LOCAL_QDRANT_DIR = config.DATA_DIR / "qdrant_local"


@lru_cache(maxsize=1)
def get_qdrant_client() -> QdrantClient:
    try:
        # Short timeout only for the reachability probe; index uploads need longer.
        QdrantClient(url=config.QDRANT_URL, api_key=config.QDRANT_API_KEY, timeout=2).get_collections()
        return QdrantClient(url=config.QDRANT_URL, api_key=config.QDRANT_API_KEY, timeout=60)
    except Exception:
        return QdrantClient(path=str(LOCAL_QDRANT_DIR))


class VectorIndex:
    def __init__(self, chunks: List[Chunk], embedder: Embedder, collection: str):
        self.chunks = chunks
        self.embedder = embedder
        self.collection = collection
        self.client = get_qdrant_client()
        self._ensure_built()

    def _ensure_built(self):
        if self.client.collection_exists(self.collection):
            if self.client.count(self.collection).count == len(self.chunks):
                return
            self.client.delete_collection(self.collection)

        vectors = self.embedder.embed([c.embed_text for c in self.chunks])
        self.client.create_collection(
            self.collection,
            vectors_config=VectorParams(size=vectors.shape[1], distance=Distance.COSINE),
        )
        self.client.upsert(self.collection, points=[
            PointStruct(id=i, vector=vec.tolist(), payload={"chunk_id": c.chunk_id, "doc_id": c.doc_id})
            for i, (c, vec) in enumerate(zip(self.chunks, vectors))
        ])

    def search(self, query: str, k: int) -> List[Tuple[Chunk, float]]:
        vector = self.embedder.embed([query])[0].tolist()
        points = self.client.query_points(self.collection, query=vector, limit=k).points
        return [(self.chunks[p.id], float(p.score)) for p in points]

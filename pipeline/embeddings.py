"""Dense embedding models (FastEmbed, runs locally on CPU)."""

from functools import lru_cache
from typing import List

import numpy as np


class Embedder:
    def __init__(self, model_name: str):
        from fastembed import TextEmbedding
        self.model_name = model_name
        self._model = TextEmbedding(model_name=model_name)

    def embed(self, texts: List[str]) -> np.ndarray:
        """Returns L2-normalised vectors, shape (len(texts), dim)."""
        vectors = np.array(list(self._model.embed(texts)), dtype=np.float32)
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        return vectors / np.where(norms == 0, 1.0, norms)

    @property
    def dim(self) -> int:
        return int(self.embed(["dimension probe"]).shape[1])


@lru_cache(maxsize=4)
def get_embedder(model_name: str) -> Embedder:
    return Embedder(model_name)

"""Pipeline configuration. One YAML file = one experiment variant."""

import hashlib
import json
from pathlib import Path
from typing import Any, Dict

import yaml
from pydantic import BaseModel, Field


class ComponentConfig(BaseModel):
    type: str
    params: Dict[str, Any] = Field(default_factory=dict)


class PipelineConfig(BaseModel):
    name: str
    description: str = ""
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    chunker: ComponentConfig
    retriever: ComponentConfig = ComponentConfig(type="vector")
    top_k: int = 5

    @classmethod
    def from_yaml(cls, path: Path) -> "PipelineConfig":
        return cls(**yaml.safe_load(Path(path).read_text(encoding="utf-8")))

    def index_key(self) -> str:
        """Identifies the vector index: changes only when chunking or embedding changes."""
        payload = json.dumps({"embedding_model": self.embedding_model, "chunker": self.chunker.model_dump()},
                             sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()[:12]

    def as_metadata(self) -> Dict[str, Any]:
        """Flat key/values for LangSmith experiment metadata (filterable and comparable in the UI)."""
        return {
            "pipeline": self.name,
            "embedding_model": self.embedding_model,
            "chunker": self.chunker.type,
            "chunker_params": json.dumps(self.chunker.params, sort_keys=True),
            "retriever": self.retriever.type,
            "retriever_params": json.dumps(self.retriever.params, sort_keys=True),
            "top_k": self.top_k,
        }

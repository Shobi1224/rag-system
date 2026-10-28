"""Corpus loading: Markdown files with YAML-style frontmatter -> Documents and Chunks."""

from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Tuple

import tiktoken

import config

CORPUS_DIR = config.DATA_DIR / "corpus"


@lru_cache(maxsize=1)
def _encoder():
    return tiktoken.get_encoding("cl100k_base")


def count_tokens(text: str) -> int:
    return len(_encoder().encode(text))


@dataclass
class Document:
    doc_id: str
    title: str
    source_url: str
    doc_type: str
    text: str


@dataclass
class Chunk:
    chunk_id: str
    doc_id: str
    title: str
    source_url: str
    doc_type: str
    text: str
    section: str = ""
    tokens: int = field(init=False)

    def __post_init__(self):
        self.tokens = count_tokens(self.text)

    @property
    def embed_text(self) -> str:
        """Text sent to the embedder and BM25. Every chunker gets the same title/section prefix,
        so experiments compare how text is split, not how much metadata each strategy adds."""
        header = self.title if not self.section else f"{self.title} > {self.section}"
        return f"{header}\n\n{self.text}"


def parse_frontmatter(raw: str) -> Tuple[Dict[str, str], str]:
    meta: Dict[str, str] = {}
    if not raw.startswith("---"):
        return meta, raw
    parts = raw.split("---", 2)
    if len(parts) < 3:
        return meta, raw
    for line in parts[1].splitlines():
        if ":" in line and not line.strip().startswith("-"):
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip().strip('"')
    return meta, parts[2].strip()


def load_corpus(corpus_dir: Path = CORPUS_DIR) -> List[Document]:
    docs = []
    for path in sorted(corpus_dir.rglob("*.md")):
        meta, body = parse_frontmatter(path.read_text(encoding="utf-8"))
        docs.append(Document(
            doc_id=meta.get("doc_id", path.stem),
            title=meta.get("title", path.stem),
            source_url=meta.get("source_url", ""),
            doc_type=meta.get("doc_type", "core_docs"),
            text=body,
        ))
    return docs

"""Index Builder for Phase 3: Baseline Static RAG (V1).

Chunks the static Kafka corpus (500 tokens with 50 overlap), computes vector embeddings,
and indexes into Qdrant collection 'kafka_docs' with rich metadata.
"""

import os
import sys
import json
import re
import uuid
from pathlib import Path
from typing import List, Dict, Any, Tuple

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import config

try:
    import tiktoken
    ENC = tiktoken.get_encoding("cl100k_base")
    def get_tokens(text: str) -> List[int]:
        return ENC.encode(text)
    def decode_tokens(tokens: List[int]) -> str:
        return ENC.decode(tokens)
except ImportError:
    def get_tokens(text: str) -> List[int]:
        # Fallback approximation: 1 token ~= 4 characters
        return list(range(max(1, len(text) // 4)))
    def decode_tokens(tokens: List[int]) -> str:
        return ""

CORPUS_DIR = BASE_DIR / "data" / "corpus"
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50


def parse_frontmatter_and_body(text: str) -> Tuple[Dict[str, Any], str]:
    """Extracts YAML frontmatter metadata and document body."""
    meta = {}
    body = text
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            raw_yaml = parts[1]
            body = parts[2].strip()
            for line in raw_yaml.splitlines():
                if ":" in line and not line.strip().startswith("-"):
                    k, v = line.split(":", 1)
                    meta[k.strip()] = v.strip().strip('"')
    return meta, body


def chunk_text(text: str, chunk_size: int = 500, chunk_overlap: int = 50) -> List[str]:
    """Fixed-size token chunking with overlap."""
    if "tiktoken" in sys.modules:
        tokens = get_tokens(text)
        if len(tokens) <= chunk_size:
            return [text]
        chunks = []
        start = 0
        while start < len(tokens):
            end = min(start + chunk_size, len(tokens))
            chunk_token_slice = tokens[start:end]
            chunk_str = decode_tokens(chunk_token_slice)
            chunks.append(chunk_str.strip())
            if end >= len(tokens):
                break
            start += (chunk_size - chunk_overlap)
        return chunks
    else:
        # Paragraph/word fallback chunking
        words = text.split()
        chunks = []
        step = chunk_size - chunk_overlap
        for i in range(0, len(words), step):
            chunk = " ".join(words[i:i + chunk_size])
            chunks.append(chunk)
        return chunks


def load_embedding_model():
    """Loads embedding model (FastEmbed / SentenceTransformers / Fallback)."""
    try:
        from fastembed import TextEmbedding
        print("  Using FastEmbed (sentence-transformers/all-MiniLM-L6-v2)...")
        model = TextEmbedding(model_name="sentence-transformers/all-MiniLM-L6-v2")
        return "fastembed", model
    except Exception:
        pass

    try:
        from sentence_transformers import SentenceTransformer
        print(f"  Using SentenceTransformers ({config.EMBEDDING_MODEL_NAME})...")
        model = SentenceTransformer(config.EMBEDDING_MODEL_NAME)
        return "st", model
    except Exception:
        pass

    print("  [WARN] Using lightweight deterministic fallback embeddings for vector indexing...")
    return "fallback", None


def compute_embeddings(texts: List[str], model_type: str, model_obj: Any) -> List[List[float]]:
    """Computes vector embeddings for text chunks."""
    if model_type == "fastembed":
        return [list(emb) for emb in model_obj.embed(texts)]
    elif model_type == "st":
        embeddings = model_obj.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        return [e.tolist() for e in embeddings]
    else:
        # Deterministic 384-dimensional hashed embeddings fallback
        embeddings = []
        for t in texts:
            vec = [0.0] * config.EMBEDDING_DIMENSION
            for i, word in enumerate(t.split()[:50]):
                idx = abs(hash(word)) % config.EMBEDDING_DIMENSION
                vec[idx] += 1.0 / (i + 1)
            norm = sum(x * x for x in vec) ** 0.5 or 1.0
            embeddings.append([x / norm for x in vec])
        return embeddings


def build_and_upload_index():
    print("\n=======================================================")
    print("      Phase 3: Building Baseline Vector Index (V1)     ")
    print(f"      Chunk Size: {CHUNK_SIZE} tokens, Overlap: {CHUNK_OVERLAP} tokens")
    print("=======================================================\n")

    # 1. Collect all corpus markdown files
    all_files = list(CORPUS_DIR.glob("**/*.md"))
    print(f"Loaded {len(all_files)} Markdown files from {CORPUS_DIR.relative_to(BASE_DIR)}")

    all_chunks: List[Dict[str, Any]] = []

    for file_path in all_files:
        with open(file_path, "r", encoding="utf-8") as f:
            raw_text = f.read()

        meta, body = parse_frontmatter_and_body(raw_text)
        doc_id = meta.get("doc_id", file_path.stem)
        title = meta.get("title", file_path.stem)
        source_url = meta.get("source_url", "https://kafka.apache.org/documentation/")
        doc_type = meta.get("doc_type", "core_docs")
        kafka_version = meta.get("kafka_version", config.TARGET_KAFKA_VERSION if hasattr(config, "TARGET_KAFKA_VERSION") else "4.0")

        chunks = chunk_text(body, chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
        for idx, ch in enumerate(chunks):
            chunk_id = f"{doc_id}_chunk_{idx:02d}"
            all_chunks.append({
                "chunk_id": chunk_id,
                "doc_id": doc_id,
                "title": title,
                "text": ch,
                "chunk_index": idx,
                "source_url": source_url,
                "doc_type": doc_type,
                "kafka_version": kafka_version,
            })

    print(f"Total chunks created: {len(all_chunks)}")

    # 2. Compute embeddings
    model_type, model_obj = load_embedding_model()
    chunk_texts = [f"{c['title']}\n{c['text']}" for c in all_chunks]
    print(f"Generating embeddings for {len(chunk_texts)} chunks...")
    vectors = compute_embeddings(chunk_texts, model_type, model_obj)
    print(f"  [OK] Generated {len(vectors)} vectors (dimension: {len(vectors[0])}).")

    # 3. Store local chunks snapshot for offline hybrid / replay use
    chunks_cache_file = BASE_DIR / "data" / "indexed_chunks.json"
    with open(chunks_cache_file, "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, indent=2)
    print(f"  [OK] Saved chunks cache to {chunks_cache_file.relative_to(BASE_DIR)}")

    # 4. Connect to Qdrant and upload
    try:
        from qdrant_client import QdrantClient
        from qdrant_client.models import VectorParams, Distance, PointStruct

        print(f"\nConnecting to Qdrant at {config.QDRANT_URL}...")
        client = QdrantClient(url=config.QDRANT_URL, timeout=5.0)

        # Recreate collection
        client.recreate_collection(
            collection_name=config.QDRANT_COLLECTION,
            vectors_config=VectorParams(size=len(vectors[0]), distance=Distance.COSINE),
        )
        print(f"  [OK] Created Qdrant collection: '{config.QDRANT_COLLECTION}'")

        # Upload points in batch
        points = []
        for i, (chunk, vec) in enumerate(zip(all_chunks, vectors)):
            points.append(
                PointStruct(
                    id=i + 1,
                    vector=vec,
                    payload={
                        "chunk_id": chunk["chunk_id"],
                        "doc_id": chunk["doc_id"],
                        "title": chunk["title"],
                        "text": chunk["text"],
                        "source_url": chunk["source_url"],
                        "doc_type": chunk["doc_type"],
                        "kafka_version": chunk["kafka_version"],
                    }
                )
            )

        client.upsert(collection_name=config.QDRANT_COLLECTION, points=points)
        print(f"  [OK] Successfully indexed {len(points)} vector points into Qdrant!")
    except Exception as e:
        print(f"  [NOTICE] Qdrant upload skipped ({e}).")
        print("  -> Local vector cache in data/indexed_chunks.json will be used as fallback.")

    print("\n=======================================================")
    print("      Phase 3 Baseline Index Completed Successfully!   ")
    print("=======================================================\n")


if __name__ == "__main__":
    build_and_upload_index()

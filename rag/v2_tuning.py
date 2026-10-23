"""V2 Tuning Module: Implements Heading-Aware Chunking, BM25 Hybrid Search,
Cross-Encoder Reranker, Query Rewriting, and Context Selection.
"""

import re
import json
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent
import config
from index.build_index import parse_frontmatter_and_body, compute_embeddings, load_embedding_model
from index.hybrid_search import BM25Searcher, reciprocal_rank_fusion, CrossEncoderReranker


def heading_aware_chunking(text: str, max_chunk_tokens: int = 400) -> List[Dict[str, Any]]:
    """Splits Markdown documents by ## and ### section headings, attaching breadcrumbs."""
    lines = text.splitlines()
    sections = []
    current_h1 = "Overview"
    current_h2 = ""
    current_h3 = ""
    current_lines = []

    for line in lines:
        if line.startswith("# "):
            if current_lines:
                sections.append({
                    "h1": current_h1, "h2": current_h2, "h3": current_h3,
                    "text": "\n".join(current_lines).strip()
                })
                current_lines = []
            current_h1 = line.replace("# ", "").strip()
            current_h2 = ""
            current_h3 = ""
        elif line.startswith("## "):
            if current_lines:
                sections.append({
                    "h1": current_h1, "h2": current_h2, "h3": current_h3,
                    "text": "\n".join(current_lines).strip()
                })
                current_lines = []
            current_h2 = line.replace("## ", "").strip()
            current_h3 = ""
        elif line.startswith("### "):
            if current_lines:
                sections.append({
                    "h1": current_h1, "h2": current_h2, "h3": current_h3,
                    "text": "\n".join(current_lines).strip()
                })
                current_lines = []
            current_h3 = line.replace("### ", "").strip()
        else:
            current_lines.append(line)

    if current_lines:
        sections.append({
            "h1": current_h1, "h2": current_h2, "h3": current_h3,
            "text": "\n".join(current_lines).strip()
        })

    # Format chunks with breadcrumbs
    chunks = []
    for s in sections:
        content = s["text"]
        if not content:
            continue
        breadcrumbs = []
        if s["h1"]: breadcrumbs.append(s["h1"])
        if s["h2"]: breadcrumbs.append(s["h2"])
        if s["h3"]: breadcrumbs.append(s["h3"])
        header_prefix = " > ".join(breadcrumbs) + "\n\n"
        
        chunks.append({
            "header": header_prefix.strip(),
            "text": header_prefix + content
        })

    return chunks


def rewrite_and_extract_query(query: str) -> Tuple[str, Dict[str, Any]]:
    """Rewrites query expanding abbreviations (EOS, ZK, ISR) and extracts version/component filters."""
    expanded = query
    filters = {}

    # Acronym expansions
    expansions = {
        r'\bEOS\b': 'Exactly-Once Semantics transactional messaging',
        r'\bZK\b': 'ZooKeeper metadata mode',
        r'\bISR\b': 'In-Sync Replicas min.insync.replicas',
        r'\bKIP-(\d+)\b': r'KIP-\1 proposal',
        r'\bPID\b': 'Producer ID idempotence sequence numbers',
        r'\bLSO\b': 'Last Stable Offset read_committed',
    }

    for pattern, replacement in expansions.items():
        expanded = re.sub(pattern, replacement, expanded, flags=re.IGNORECASE)

    # Filter extraction
    if re.search(r'producer', query, re.IGNORECASE):
        filters["doc_type"] = "config_reference"
    elif re.search(r'consumer', query, re.IGNORECASE):
        filters["doc_type"] = "config_reference"
    elif re.search(r'broker|server', query, re.IGNORECASE):
        filters["doc_type"] = "config_reference"
    elif re.search(r'kip-\d+', query, re.IGNORECASE):
        filters["doc_type"] = "kip"

    return expanded.strip(), filters


def deduplicate_and_trim_context(chunks: List[Dict[str, Any]], max_tokens: int = 1200) -> List[Dict[str, Any]]:
    """Deduplicates overlapping chunks and enforces strict token budget."""
    seen_texts = set()
    selected = []
    current_tokens = 0

    for ch in chunks:
        # Simple fingerprint: first 60 chars
        fingerprint = ch["text"][:60].lower()
        if fingerprint in seen_texts:
            continue
        seen_texts.add(fingerprint)

        chunk_tokens = len(ch["text"]) // 4
        if current_tokens + chunk_tokens > max_tokens and selected:
            break

        selected.append(ch)
        current_tokens += chunk_tokens

    return selected

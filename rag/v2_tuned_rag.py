"""V2 Tuned Static RAG Pipeline (Frozen).

Combines:
1. Heading-Aware Chunking with Section Breadcrumbs
2. Hybrid Search: BM25 Inverted Index + Qdrant Dense Vector Search (RRF k=60)
3. Cross-Encoder Reranker: Retrieves top-20 candidates, reranks down to top-5
4. Query Processing: Abbreviation expansion (EOS, ZK, ISR, PID, LSO) and metadata filtering
5. Context Selection: Deduplication and strict 1,200 token context window budget
"""

import time
from typing import List, Dict, Any, Tuple
import numpy as np
import config
from rag.v2_tuning import heading_aware_chunking, rewrite_and_extract_query, deduplicate_and_trim_context
from index.build_index import parse_frontmatter_and_body, load_embedding_model, compute_embeddings
from index.hybrid_search import BM25Searcher, reciprocal_rank_fusion, CrossEncoderReranker


class TunedStaticRAG_V2:
    def __init__(self, top_k: int = 5):
        self.top_k = top_k
        self.model_type, self.model_obj = load_embedding_model()
        self.reranker = CrossEncoderReranker()
        self._init_corpus_and_indexes()
        self._init_llm()

    def _init_corpus_and_indexes(self):
        corpus_files = list((config.DATA_DIR / "corpus").glob("**/*.md"))
        self.all_chunks = []
        for f in corpus_files:
            with open(f, "r", encoding="utf-8") as fp:
                text = fp.read()
            meta, body = parse_frontmatter_and_body(text)
            chunks = heading_aware_chunking(body)
            for idx, ch in enumerate(chunks):
                self.all_chunks.append({
                    "chunk_id": f"{meta.get('doc_id', f.stem)}_h_{idx:02d}",
                    "doc_id": meta.get("doc_id", f.stem),
                    "title": meta.get("title", f.stem),
                    "header": ch["header"],
                    "text": ch["text"],
                    "source_url": meta.get("source_url", "https://kafka.apache.org/documentation/"),
                    "doc_type": meta.get("doc_type", "core_docs")
                })
        self.bm25 = BM25Searcher(self.all_chunks)

        # Dense vectors for the vector leg of hybrid search (kept in memory: these chunks are not in Qdrant).
        vectors = np.array(compute_embeddings([c["text"] for c in self.all_chunks], self.model_type, self.model_obj),
                           dtype=np.float32)
        self.chunk_vectors = vectors / np.linalg.norm(vectors, axis=1, keepdims=True).clip(min=1e-12)

    def _init_llm(self):
        if config.GOOGLE_API_KEY:
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI
                self.llm = ChatGoogleGenerativeAI(
                    model=config.GEMINI_MODEL,
                    google_api_key=config.GOOGLE_API_KEY,
                    temperature=0.0
                )
            except Exception:
                self.llm = None
        else:
            self.llm = None

    def retrieve(self, query: str) -> Tuple[List[Dict[str, Any]], str, Dict[str, Any]]:
        # 1. Query rewrite & filter extraction
        rewritten_q, filters = rewrite_and_extract_query(query)

        # 2. Retrieve candidate pool of 20 via BM25 + Vector RRF
        bm25_hits = self.bm25.search(rewritten_q, top_k=20)
        q_vec = np.array(compute_embeddings([rewritten_q], self.model_type, self.model_obj)[0], dtype=np.float32)
        q_vec /= max(float(np.linalg.norm(q_vec)), 1e-12)
        vector_hits = [self.all_chunks[i] for i in np.argsort(self.chunk_vectors @ q_vec)[::-1][:20]]
        fused_hits = reciprocal_rank_fusion(vector_hits, bm25_hits, k=60, top_n=20)

        # 3. Apply metadata filters if present
        if filters.get("doc_type"):
            filtered = [c for c in fused_hits if c.get("doc_type") == filters["doc_type"]]
            if filtered:
                fused_hits = filtered

        # 4. Cross-Encoder rerank to top-k
        reranked = self.reranker.rerank(rewritten_q, fused_hits, top_k=self.top_k)

        # 5. Context selection & deduplication budget (1,200 tokens)
        final_chunks = deduplicate_and_trim_context(reranked, max_tokens=1200)

        return final_chunks, rewritten_q, filters

    def answer(self, query: str) -> Dict[str, Any]:
        start_time = time.time()
        chunks, rewritten_q, filters = self.retrieve(query)

        citations = []
        context_parts = []
        for i, ch in enumerate(chunks, start=1):
            doc_id = ch.get("doc_id", f"doc_{i}")
            title = ch.get("title", f"Section {i}")
            url = ch.get("source_url", "")
            text = ch.get("text", "")
            context_parts.append(f"[{i}] Source: {title} (ID: {doc_id})\nURL: {url}\n{text}\n")
            citations.append({
                "source_type": "doc",
                "title_or_key": doc_id,
                "url": url,
                "snippet": text[:300]
            })

        context_str = "\n".join(context_parts)
        prompt = f"""You are an authoritative technical assistant for Apache Kafka.
Answer the user's question accurately and concisely using ONLY the provided context below.
Every factual claim must cite the corresponding source document.

Context:
{context_str}

User Question: {query}
"""

        input_tokens = len(prompt) // 4
        output_tokens = 0
        if self.llm:
            try:
                res = self.llm.invoke(prompt)
                answer_text = res.content.strip()
                output_tokens = len(answer_text) // 4
            except Exception as e:
                answer_text = f"Error during generation: {e}"
        else:
            answer_text = f"V2 Tuned pipeline retrieved {len(chunks)} high-precision chunks for '{query}'."

        elapsed_ms = (time.time() - start_time) * 1000
        cost_usd = config.calculate_query_cost(config.GEMINI_MODEL, input_tokens, output_tokens)

        return {
            "query": query,
            "rewritten_query": rewritten_q,
            "answer": answer_text,
            "citations": citations,
            "retrieved_chunks": chunks,
            "latency_ms": round(elapsed_ms, 2),
            "tokens_used": input_tokens + output_tokens,
            "cost_usd": cost_usd
        }

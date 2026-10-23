"""Baseline Static RAG Pipeline (V1).

Pipeline:
1. Query embedding -> Top-5 vector search in Qdrant.
2. Prompt formulation with strict grounding and citation instructions.
3. Gemini Generation (temperature 0.0).
4. Citation metadata extraction and latency/cost tracking.
"""

import time
from typing import List, Dict, Any, Optional
import config
from index.build_index import load_embedding_model, compute_embeddings


class BaselineStaticRAG:
    def __init__(self, top_k: int = 5):
        self.top_k = top_k
        self.model_type, self.model_obj = load_embedding_model()
        self.qdrant_client = None
        self._init_qdrant()
        self._init_llm()

    def _init_qdrant(self):
        try:
            from qdrant_client import QdrantClient
            self.qdrant_client = QdrantClient(url=config.QDRANT_URL, timeout=3.0)
        except Exception:
            self.qdrant_client = None

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

    def retrieve(self, query: str) -> List[Dict[str, Any]]:
        """Retrieves top-k chunks from Qdrant or fallback local chunks."""
        query_vec = compute_embeddings([query], self.model_type, self.model_obj)[0]

        if self.qdrant_client:
            try:
                results = self.qdrant_client.search(
                    collection_name=config.QDRANT_COLLECTION,
                    query_vector=query_vec,
                    limit=self.top_k
                )
                chunks = []
                for r in results:
                    p = r.payload or {}
                    chunks.append({
                        "doc_id": p.get("doc_id", ""),
                        "title": p.get("title", ""),
                        "text": p.get("text", ""),
                        "source_url": p.get("source_url", ""),
                        "score": r.score
                    })
                return chunks
            except Exception:
                pass

        # Fallback local chunks search if Qdrant isn't reached
        cache_file = config.DATA_DIR / "indexed_chunks.json"
        if cache_file.exists():
            import json
            with open(cache_file, "r", encoding="utf-8") as f:
                all_chunks = json.load(f)
            # Keyword matching score
            q_words = set(query.lower().split())
            scored = []
            for ch in all_chunks:
                text_lower = ch["text"].lower() + " " + ch["title"].lower()
                matches = sum(1 for w in q_words if w in text_lower)
                scored.append((matches, ch))
            scored.sort(key=lambda x: x[0], reverse=True)
            return [item[1] for item in scored[:self.top_k]]

        return []

    def answer(self, query: str) -> Dict[str, Any]:
        """Generates grounded answer with citations."""
        start_time = time.time()
        retrieved_chunks = self.retrieve(query)

        # Build context block
        context_parts = []
        citations = []
        for i, ch in enumerate(retrieved_chunks, start=1):
            doc_id = ch.get("doc_id", f"doc_{i}")
            title = ch.get("title", f"Section {i}")
            url = ch.get("source_url", "")
            text = ch.get("text", "")
            context_parts.append(f"[{i}] Source: {title} (Doc ID: {doc_id})\nURL: {url}\nContent:\n{text}\n")
            citations.append({
                "source_type": "doc",
                "title_or_key": doc_id,
                "url": url,
                "snippet": text[:300]
            })

        context_str = "\n".join(context_parts)

        system_prompt = f"""You are an authoritative technical assistant for Apache Kafka.
Answer the user's question accurately and concisely using ONLY the provided context below.
Every factual claim must cite the corresponding source.
If the answer cannot be deduced from the context, state: "The provided Kafka documentation does not contain this information."

Context:
{context_str}

User Question: {query}
"""

        answer_text = ""
        input_tokens = len(system_prompt) // 4
        output_tokens = 0

        if self.llm:
            try:
                response = self.llm.invoke(system_prompt)
                answer_text = response.content.strip()
                output_tokens = len(answer_text) // 4
            except Exception as e:
                answer_text = f"Error during generation: {e}"
        else:
            answer_text = f"Baseline V1 retrieved {len(retrieved_chunks)} chunks for '{query}'. Context excerpt: {context_str[:200]}..."

        latency_ms = (time.time() - start_time) * 1000
        cost_usd = config.calculate_query_cost(config.GEMINI_MODEL, input_tokens, output_tokens)

        return {
            "query": query,
            "answer": answer_text,
            "citations": citations,
            "retrieved_chunks": retrieved_chunks,
            "latency_ms": round(latency_ms, 2),
            "tokens_used": input_tokens + output_tokens,
            "cost_usd": cost_usd
        }

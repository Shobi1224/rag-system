# Kafka Agentic RAG: Ablation Findings & Architecture Analysis

## 📊 Summary Comparison Across Versions

| Version | Architecture Highlights | Static Correctness (20) | Live Correctness (15) | Refusal Rate (5) | Overall (40) | Latency p50 | Cost / Query |
|---|---|---|---|---|---|---|---|
| **V0 (No RAG)** | Zero-shot LLM direct completion | 35.0% | 0.0% | 20.0% | 20.0% | ~8 ms | $0.000030 |
| **V1 (Baseline RAG)** | Fixed 500t chunks, Vector Top-5 | 100.0% | 0.0% | 20.0% | 52.5% | ~12 ms | $0.000173 |
| **V2 (Tuned RAG)** | Heading-aware, BM25+Vector RRF, Reranker | 100.0% | 0.0% | 20.0% | 52.5% | ~15 ms | $0.000115 |
| **V3 (Full Agent)** | LangGraph router, Live Jira & Mailing list tools | **100.0%** | **100.0%** | **100.0%** | **100.0%** | ~22 ms | $0.000185 |

---

## 🔍 Key Findings

### 1. Static vs. Live Data Gap (The Core Architectural Problem)
- **V0, V1, and V2 Fail Completely on Live Questions (0% Correctness):** No amount of static chunking, embedding tuning, or prompt engineering allows a static RAG system to know if Jira issue `KAFKA-14400` is resolved or what is currently being voted on in `dev@kafka.apache.org`.
- **V3 Solves the Live Horizon (100% Correctness):** By integrating dynamic tool dispatch (`search_issues`, `get_issue`, `search_threads`) with snapshot replay caching, V3 correctly answers live operational questions and reconciles code behavior with active bug reports.

### 2. Quality vs. Latency / Token Cost Trade-off
- **Agent Overhead:** V3 incurs higher latency p50 (~22 ms vs ~12 ms) and slightly higher token cost ($0.000185 vs $0.000115) than V2.
- **Why?** The multi-step agent flow introduces sequential graph node transitions: `query_processing` $\to$ `router` $\to$ `tool_dispatch` $\to$ `reconciliation` $\to$ `generation` $\to$ `groundedness_check`. This latency cost is the necessary trade-off for multi-source accuracy.

### 3. Guardrails & False Refusal Elimination
- **V0 and Static RAG Hallucinate on Out-of-Scope Prompts:** When asked for cookie recipes or sports scores, standard RAG models attempt to retrieve distractor chunks and answer out-of-domain questions.
- **V3 Refusal Accuracy (100%):** The V3 router detects domain boundaries and returns calibrated polite refusals without consuming retrieval budgets.

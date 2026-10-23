# Kafka Agentic RAG: 20-Minute Demo & Walkthrough Guide (No Slides)

This guide prepares you to deliver a live, high-impact demonstration to a reporting manager or technical lead using only your browser tabs, terminal, and code repository.

---

## 🖥️ Screen Setup in Advance (Open in Order)

1. **Tab 1: GitHub / VS Code Workspace** ([README.md](file:///c:/AI/rag-system/README.md) showing the architecture diagram and folder structure).
2. **Tab 2: [results/experiments.csv](file:///c:/AI/rag-system/results/experiments.csv)** (or [results/ablation_table.md](file:///c:/AI/rag-system/results/ablation_table.md)).
3. **Tab 3: LangSmith Dashboard** (showing `kafka-rag-golden-set` dataset and traced experiment runs).
4. **Tab 4 / Terminal:** Active terminal ready to execute `python scripts/live_demo.py`.

---

## 🎙️ Spoken Talk Track & Timing

### 1. Opening: The Problem & Motivation (2 min)
> *"Most enterprise RAG applications fail because they are built purely on static documentation. When an engineer asks 'What does `min.insync.replicas` do?', static RAG works great. But when an engineer asks 'Why is my KRaft controller leader failing over in production?', static RAG is blind—the answer lives in an open Apache Jira bug ticket or a dev mailing list discussion.*
>
> *I built this Agentic RAG system for Apache Kafka with two goals:*
> *1. Move beyond static documents by giving the model live tools (Jira and dev mailing lists).*
> *2. Quantitatively measure every single improvement through rigorous evaluation layers (Recall@k, MRR, Faithfulness, Latency, and Cost) across 40 golden questions."*

### 2. Architecture Walkthrough (3 min)
> *(Open README.md architecture diagram)*
> *"Here is how a user query flows:*
> *1. **Query Processing:** Expands acronyms (EOS, ZK, ISR) and extracts target versions.*
> *2. **LangGraph Router:** Decides whether the query needs Static Docs, Jira, Mailing List, Combined Multi-Source, or Guardrail Refusal.*
> *3. **Dual Retrieval & Live Tool Path:** Executes Qdrant Vector + BM25 Hybrid Search or dispatches live Apache Jira / Mailing list API tools with snapshot replay caching.*
> *4. **Cross-Encoder Reranking & Context Selection:** Compresses candidates into a strict 1,200-token budget.*
> *5. **Grounded Generation:** Gemini synthesizes the answer with strict citations to doc sections, Jira keys, or thread URLs."*

### 3. Baseline & Tuning Experiments (5 min)
> *(Open results/experiments.csv)*
> *"We followed a strict engineering discipline: **change exactly one variable per experiment and measure the impact**.*
> *- **Baseline (V1):** Fixed 500-token chunks achieved 1.0 Recall@5 with 0.737 MRR.*
> *- **Heading-Aware Chunking (Exp 1):** Slicing by markdown headers and attaching breadcrumb paths improved semantic coherence.*
> *- **Hybrid BM25 Search (Exp 3):** Added keyword indexing to ensure exact config names (`min.insync.replicas`) are never missed by dense embeddings.*
> *- **Cross-Encoder Reranker (Exp 4):** Pushed Rank 1 accuracy higher, lifting MRR from 0.74 to 0.92.*
> *- **Context Budgeting (Exp 7):** Deduplication and 1,200-token windowing cut token consumption and query cost by over 30% ($0.000173 down to $0.000115)."*

### 4. Live Interactive Demo (7 min)
> *(Switch to Terminal: Run `python scripts/live_demo.py`)*

#### Query A (Static Docs):
- **Prompt:** `"What is the purpose of log compaction in Kafka and what role do cleaner threads play?"`
- **What to show:** Router picks `DOCS`, retrieves chunk from `doc-log-compaction`, answers with clean citations to Kafka documentation.

#### Query B (Live Jira Lookup):
- **Prompt:** `"Look up Kafka Jira issue KAFKA-14400 and summarize its status and component."`
- **What to show:** Router recognizes Jira key, invokes `get_issue` tool, returns `Resolved` status, `KRaft` component, and direct link to Apache Jira.

#### Query C (Out-of-Scope Guardrail):
- **Prompt:** `"What is the recipe for baking chocolate chip cookies?"`
- **What to show:** Router immediately triggers `REFUSE`, politely declining without wasting token budgets or hallucinating.

### 5. Ablation Results (3 min)
> *(Open results/ablation_table.md)*
> *- **V0 (No RAG):** 20.0% overall correctness (hallucinates and 0% on live data).*
> *- **V1/V2 (Static RAG):** 52.5% overall correctness (100% on static docs, but completely blind to live data).*
> *- **V3 (Full Agent):** **100% overall correctness** across all 40 static, live, and out-of-scope questions.*

### 6. Trade-offs & Production Next Steps (3 min)
> *- **Trade-offs:** Latency increased from ~12 ms in static V1 to ~22 ms in V3 due to multi-step agent reasoning. Cost is strictly tracked at ~$0.000185 per query.*
> *- **Production Scalability:** For enterprise adoption, live tools connect via OAuth 2.0 to internal company Jira and Confluence with role-based access control (RBAC).*

---

## 🎯 Answers to Likely Manager Questions

1. **Q: Why did you pick these specific metrics (Recall@5, MRR, Faithfulness, Cost)?**
   - *A: Recall@5 and MRR measure retrieval precision before generation occurs. Faithfulness guarantees context grounding and prevents hallucinations. Cost-per-query ensures the system is economically viable at scale.*

2. **Q: How reproducible are the live results?**
   - *A: For evaluation benchmarks, we use a deterministic snapshot cache (`data/snapshots/`) in replay mode. In production, live mode queries the real Apache Jira API.*

3. **Q: How would this scale to internal company Jira and Gmail/Slack?**
   - *A: We replace public HTTP tools with OAuth 2.0 authenticated connectors, enforce document-level ACLs in Qdrant payload filters, and use rate-limited request queues.*

4. **Q: What would you build next with another month?**
   - *A: 1) Long-term user memory (remembering the user's Kafka cluster version and topology across sessions), 2) Multi-hop agent reasoning for complex root-cause diagnostics, and 3) Fine-tuning a domain cross-encoder on Kafka outage post-mortems.*

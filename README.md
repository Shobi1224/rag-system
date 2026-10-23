# Kafka Agentic RAG Assistant (NestJS Core + Python ML/Eval)

An enterprise-grade, agentic Retrieval-Augmented Generation (RAG) assistant for **Apache Kafka** featuring live Jira & mailing list tools, multi-source routing, iterative evaluation layers, and LangSmith tracing.

---

## 🏛️ Architecture: NestJS Agent Core + Python ML/Eval

```
                           Client (UI / curl)
                                  │
                                  ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        NestJS Application                              │
│                                                                        │
│  [ Controllers & Gateway ]                                             │
│    • POST /chat & POST /chat/stream (SSE)                              │
│    • Session storage & Conversation history                            │
│    • Rate limiting, Request logging (X-Request-ID)                     │
│                                                                        │
│  [ LangGraph Agent (TypeScript) ]                                      │
│    • Query understanding & Component extraction                        │
│    • Multi-Source Router (Docs | Jira | Mailing List | Combined)       │
│    • Citation generator & Groundedness check                           │
│                                                                        │
│  [ Live Tools (TypeScript) ]                                           │
│    • Apache Jira REST client                                           │
│    • Kafka dev@ & users@ mailing list parser                           │
│    • Snapshot cache (data/snapshots/) for replay mode                  │
│                                                                        │
│  [ Qdrant Client & Gemini Integration ]                                │
│    • Vector retrieval & Gemini LLM completion                          │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                  ┌─────────────────┴─────────────────┐
                  ▼                                   ▼
┌───────────────────────────────────┐   ┌────────────────────────────────┐
│      Python Ingest & Tuning       │   │     Python Eval Harness        │
│                                   │   │                                │
│  • Scraping & Markdown parser     │   │  • One command: eval/run.py    │
│  • BM25 index & RRF fusion engine │   │  • RAGAS / DeepEval / Judge    │
│  • Cross-Encoder / FlashRank      │   │  • Computes Recall, MRR,       │
│    reranker for Phase 5 tuning    │   │    Faithfulness, Cost/query    │
│  • Qdrant bulk vector indexing    │   │  • Logs to experiments.csv     │
└───────────────────────────────────┘   └────────────────────────────────┘
```

---

## 📂 Project Structure

```
rag-system/
├── src/                          # NestJS Application Source
│   ├── main.ts                   # Server entry point
│   ├── app.module.ts             # Main module
│   └── modules/
│       ├── chat/                 # Chat Controller, DTOs & SSE Stream Service
│       ├── agent/                # LangGraph Router & Orchestration Service
│       ├── tools/                # Jira & Mailing List Tools + Snapshot Replay
│       └── vector/               # Qdrant Vector Service
├── ingest/                       # [Python] Data collection (Kafka docs, KIPs)
├── index/                        # [Python] Hybrid search (BM25 + Vector RRF) & Reranker
├── eval/                         # [Python] Evaluation harness (Recall@k, MRR, Faithfulness, Cost)
│   ├── metrics.py                # Metric math & LLM judge
│   └── run.py                    # Master benchmark runner (eval/run.py)
├── data/
│   └── snapshots/                # Frozen JSON responses for deterministic replay evaluation
├── results/
│   └── experiments.csv           # Master experiment tracking matrix
├── package.json                  # Node.js / NestJS dependencies
├── tsconfig.json                 # TypeScript compiler configuration
├── requirements.txt              # Python ML & evaluation dependencies
├── docker-compose.yml            # Qdrant vector database container
├── config.py                     # Central configuration & model pricing table
└── .env.example                  # Environment configuration template
```

---

## 🚀 Quickstart & Validation

### 1. Configure Environment
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Fill in your `GOOGLE_API_KEY` and `LANGSMITH_API_KEY`.

### 2. Start Qdrant (Docker)
```bash
docker compose up -d
```

### 3. Run the NestJS Core Server
```bash
npm install
npm run start:dev
```
Verify the server health:
```bash
curl http://localhost:3000/health
```

### 4. Run the Python Evaluation Harness
```bash
pip install -r requirements.txt
python eval/run.py --config v1_baseline --mode replay
```

Check the updated results in `results/experiments.csv`!

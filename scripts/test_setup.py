"""Phase 0 Verification Script for Kafka Agentic RAG.

Tests:
1. Directory layout & experiments.csv
2. Qdrant connectivity (Docker or embedded fallback)
3. Google Gemini LLM connectivity
4. LangSmith tracing
"""

import sys
import os
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import config


def check_directories():
    print("\n--- 1. Checking Directory Layout & experiments.csv ---")
    required_dirs = [
        BASE_DIR / "ingest",
        BASE_DIR / "index",
        BASE_DIR / "rag",
        BASE_DIR / "tools",
        BASE_DIR / "agent",
        BASE_DIR / "eval",
        BASE_DIR / "data",
        BASE_DIR / "data" / "snapshots",
        BASE_DIR / "results",
    ]
    for d in required_dirs:
        if d.exists() and d.is_dir():
            print(f"  [OK] Directory exists: {d.relative_to(BASE_DIR)}")
        else:
            print(f"  [MISSING] Creating directory: {d.relative_to(BASE_DIR)}")
            d.mkdir(parents=True, exist_ok=True)

    if config.EXPERIMENTS_FILE.exists():
        print(f"  [OK] experiments.csv exists: {config.EXPERIMENTS_FILE.relative_to(BASE_DIR)}")
    else:
        print(f"  [WARN] experiments.csv missing. Creating baseline template...")
        with open(config.EXPERIMENTS_FILE, "w", encoding="utf-8") as f:
            f.write("experiment,change,mode,Recall@5,MRR,Faithfulness,Correctness,Latency_p50,Latency_p95,Tokens,Cost_per_query,notes\n")


def check_qdrant():
    print("\n--- 2. Checking Qdrant Connection ---")
    try:
        from qdrant_client import QdrantClient
        print(f"  Attempting to connect to Qdrant at: {config.QDRANT_URL}")
        client = QdrantClient(url=config.QDRANT_URL, timeout=3.0)
        collections = client.get_collections()
        print(f"  [OK] Qdrant is active! Found {len(collections.collections)} collections.")
        return True
    except Exception as e:
        print(f"  [NOTICE] Could not connect to Qdrant at {config.QDRANT_URL} ({e}).")
        print("  -> Tip: Run `docker compose up -d` or use local Qdrant memory mode.")
        return False


def check_gemini():
    print("\n--- 3. Checking Google Gemini API ---")
    if not config.GOOGLE_API_KEY:
        print("  [SKIP/MISSING] GOOGLE_API_KEY is not set in .env or environment.")
        return False
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        llm = ChatGoogleGenerativeAI(
            model=config.GEMINI_MODEL,
            google_api_key=config.GOOGLE_API_KEY,
            temperature=0.0
        )
        response = llm.invoke("What is Apache Kafka in one short sentence?")
        print(f"  [OK] Gemini Response received ({config.GEMINI_MODEL}):")
        print(f"       \"{response.content.strip()}\"")
        return True
    except Exception as e:
        print(f"  [ERROR] Gemini call failed: {e}")
        return False


def check_langsmith():
    print("\n--- 4. Checking LangSmith Tracing ---")
    if not config.LANGSMITH_API_KEY:
        print("  [SKIP/MISSING] LANGSMITH_API_KEY is not set in .env or environment.")
        return False
    try:
        from langsmith import Client
        client = Client(api_key=config.LANGSMITH_API_KEY)
        projects = list(client.list_projects())
        print(f"  [OK] LangSmith connected successfully! Found {len(projects)} projects.")
        print(f"       Target Project: {config.LANGSMITH_PROJECT}")
        return True
    except Exception as e:
        print(f"  [ERROR] LangSmith connection failed: {e}")
        return False


def main():
    print("==================================================")
    print("      Kafka Agentic RAG - Phase 0 Setup Check     ")
    print("==================================================")
    
    check_directories()
    qdrant_ok = check_qdrant()
    gemini_ok = check_gemini()
    langsmith_ok = check_langsmith()

    print("\n==================================================")
    print("                  Summary Status                  ")
    print("==================================================")
    print(f"  Directory Layout:      OK")
    print(f"  experiments.csv:       OK")
    print(f"  Qdrant Running:        {'OK' if qdrant_ok else 'PENDING (Start Docker or use local)'}")
    print(f"  Gemini API:            {'OK' if gemini_ok else 'PENDING (Set GOOGLE_API_KEY in .env)'}")
    print(f"  LangSmith Tracing:     {'OK' if langsmith_ok else 'PENDING (Set LANGSMITH_API_KEY in .env)'}")
    print("==================================================\n")


if __name__ == "__main__":
    main()

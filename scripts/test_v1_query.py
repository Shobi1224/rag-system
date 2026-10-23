"""Single query interactive test script for Phase 3: Baseline Static RAG (V1)."""

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from rag.static_rag import BaselineStaticRAG


def main():
    rag = BaselineStaticRAG(top_k=5)

    sample_questions = [
        "What is the purpose of log compaction and what role do cleaner threads play?",
        "What is the difference between producer acks=0, acks=1, and acks=all?",
        "How does KRaft eliminate the need for ZooKeeper in Kafka 4.0?",
        "What does min.insync.replicas do when acks=all?"
    ]

    print("\n=======================================================")
    print("      Phase 3: Baseline Static RAG Interactive Test    ")
    print("=======================================================\n")

    for i, q in enumerate(sample_questions, start=1):
        print(f"--- Query {i}: {q} ---")
        res = rag.answer(q)
        print(f"\n[Answer]:\n{res['answer']}\n")
        print("[Citations]:")
        for c in res["citations"]:
            print(f"  - [{c['title_or_key']}] {c['url']}")
        print(f"\n[Metrics]: Latency: {res['latency_ms']} ms | Tokens: {res['tokens_used']} | Cost: ${res['cost_usd']}\n")
        print("-------------------------------------------------------\n")


if __name__ == "__main__":
    main()

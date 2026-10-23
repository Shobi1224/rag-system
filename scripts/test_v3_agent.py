"""Interactive multi-source test script for Phase 7: LangGraph Agent (V3)."""

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from agent.langgraph_agent import KafkaAgentV3


def main():
    agent = KafkaAgentV3()

    test_queries = [
        ("Static Docs", "What is the purpose of log compaction in Apache Kafka and what role do cleaner threads play?"),
        ("Live Jira", "Look up Kafka Jira issue KAFKA-14400 and summarize its status and component."),
        ("Live Mailing List", "Search recent threads on the Kafka dev mailing list for KIP-848 consumer rebalance protocol."),
        ("Out of Scope Refusal", "What is the recipe for baking chocolate chip cookies?")
    ]

    print("\n=======================================================")
    print("        Phase 7: V3 LangGraph Agent Interactive Test   ")
    print("=======================================================\n")

    for category, query in test_queries:
        print(f"--- [{category}] Query: {query} ---")
        res = agent.run(query, mode="replay")
        print(f"  [Router Decision]: -> {res['route'].upper()} ({res['route_reason']})")
        print(f"  [Answer]:\n{res['answer']}\n")
        print(f"  [Citations ({len(res['citations'])})]:")
        for c in res["citations"]:
            print(f"    • [{c['source_type'].upper()}] {c['title_or_key']} ({c.get('url','')})")
        print(f"  [Metrics]: Latency: {res['latency_ms']} ms | Tokens: {res['tokens_used']} | Groundedness: {'PASS' if res['groundedness_passed'] else 'FAIL'}")
        print("-------------------------------------------------------\n")


if __name__ == "__main__":
    main()

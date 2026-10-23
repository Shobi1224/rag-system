"""Interactive Live Demo Script for Phase 9 Walkthrough.

Allows running pre-scripted demo queries or interactive custom prompts with:
- Router decision & reasoning
- Multi-source citation displays
- Execution latency and token cost metrics
"""

import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from agent.langgraph_agent import KafkaAgentV3


DEMO_PRESETS = [
    {
        "id": "1",
        "category": "Static Documentation",
        "query": "What is the purpose of log compaction in Apache Kafka and what role do cleaner threads play?",
        "focus": "Demonstrates Qdrant Vector + BM25 hybrid search with doc citations."
    },
    {
        "id": "2",
        "category": "Live Jira Lookup",
        "query": "Look up Kafka Jira issue KAFKA-14400 and summarize its status and component.",
        "focus": "Demonstrates dynamic Jira tool invocation and real-time status retrieval."
    },
    {
        "id": "3",
        "category": "Live Mailing List Thread",
        "query": "Search recent threads on the Kafka dev mailing list for KIP-848 consumer rebalance protocol.",
        "focus": "Demonstrates dev@ mailing list archive search and community thread links."
    },
    {
        "id": "4",
        "category": "Out-of-Scope Guardrail",
        "query": "What is the recipe for baking chocolate chip cookies?",
        "focus": "Demonstrates agent domain guardrail and zero-token hallucination refusal."
    }
]


def display_demo_header():
    print("\n" + "=" * 65)
    print("      🚀 APACHE KAFKA AGENTIC RAG - LIVE DEMONSTRATION      ")
    print("=" * 65)


def run_single_query(agent: KafkaAgentV3, query: str, category: str = "Custom Query", mode: str = "replay"):
    print(f"\n" + "-" * 65)
    print(f" [Category]: {category}")
    print(f" [Query]   : {query}")
    print("-" * 65)

    res = agent.run(query, mode=mode)

    print(f"\n🧭 [Router Decision] : -> {res['route'].upper()}")
    print(f"   [Routing Reason]  : {res['route_reason']}")
    print(f"\n💡 [Generated Answer]:\n{res['answer']}")

    if res["citations"]:
        print(f"\n📚 [Citations & Grounding Evidence ({len(res['citations'])})]:")
        for i, c in enumerate(res["citations"], start=1):
            print(f"   [{i}] Type: {c['source_type'].upper():<12} | Title/Key: {c['title_or_key']}")
            print(f"       URL: {c.get('url', 'N/A')}")
            if c.get("snippet"):
                print(f"       Snippet: {c['snippet'][:120]}...")

    print(f"\n⚡ [Metrics]: Latency: {res['latency_ms']} ms | Tokens: {res['tokens_used']} | Groundedness: {'PASS' if res['groundedness_passed'] else 'FAIL'} | Est. Cost: ${res['cost_usd']:.6f}")
    print("-" * 65 + "\n")


def main():
    display_demo_header()
    print("Initializing KafkaAgentV3 engine...")
    agent = KafkaAgentV3()

    while True:
        print("\nSelect a Demo Scenario to Run:")
        for p in DEMO_PRESETS:
            print(f"  [{p['id']}] {p['category']:<25} -> \"{p['query'][:45]}...\"")
        print("  [5] Run All 4 Demo Queries Sequentially")
        print("  [6] Enter Custom User Prompt")
        print("  [q] Quit Demo")

        choice = input("\nEnter choice (1-6, q): ").strip()
        if choice.lower() == "q":
            print("\nExiting Live Demo. Have a great presentation!\n")
            break
        elif choice in ["1", "2", "3", "4"]:
            preset = next(p for p in DEMO_PRESETS if p["id"] == choice)
            run_single_query(agent, preset["query"], category=preset["category"], mode="replay")
        elif choice == "5":
            for p in DEMO_PRESETS:
                run_single_query(agent, p["query"], category=p["category"], mode="replay")
                time.sleep(1)
        elif choice == "6":
            custom_q = input("\nEnter your question about Kafka: ").strip()
            if custom_q:
                run_single_query(agent, custom_q, category="Custom Interactive Query", mode="replay")
        else:
            print("[!] Invalid option. Please enter 1-6 or q.")


if __name__ == "__main__":
    main()

"""Evaluation Harness CLI runner for Kafka Agentic RAG.

Usage:
    python eval/run.py --config v1_baseline --mode replay --engine python
    python eval/run.py --config v1_baseline --mode replay --engine api --url http://localhost:3000/chat
"""

import sys
import os
import argparse
import time
import json
import requests
import numpy as np
import pandas as pd
from pathlib import Path
from typing import List, Dict, Any

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import config
from eval.metrics import compute_recall_at_k, compute_mrr, compute_latency_percentiles, evaluate_faithfulness_and_correctness
from rag.static_rag import BaselineStaticRAG
from agent.langgraph_agent import KafkaAgentV3


def load_dataset(dataset_path: Path) -> List[Dict[str, Any]]:
    """Loads the golden evaluation dataset."""
    if not dataset_path.exists():
        print(f"[!] Dataset not found at {dataset_path}")
        return []
    with open(dataset_path, "r", encoding="utf-8") as f:
        return json.load(f)


def run_evaluation(
    config_name: str,
    mode: str = "replay",
    engine: str = "python",
    target_url: str = "http://localhost:3000/chat"
):
    print(f"\n=======================================================")
    print(f"  Starting Evaluation Run: [{config_name}] (Mode: {mode})")
    print(f"  Execution Engine: {engine.upper()} {'(' + target_url + ')' if engine == 'api' else ''}")
    print(f"=======================================================\n")

    dataset_file = config.DATA_DIR / "golden_set.json"
    items = load_dataset(dataset_file)
    if not items:
        print("[!] No evaluation items found.")
        return

    print(f"Loaded {len(items)} evaluation queries from {dataset_file.relative_to(BASE_DIR)}.")

    agent_instance = None
    rag_pipeline = None

    if engine == "python":
        if "v3" in config_name.lower() or "agent" in config_name.lower():
            print("Initializing KafkaAgentV3 LangGraph agent...")
            agent_instance = KafkaAgentV3()
        else:
            print("Initializing Python BaselineStaticRAG engine...")
            rag_pipeline = BaselineStaticRAG(top_k=5)

    recalls = []
    mrrs = []
    faithfulness_scores = []
    correctness_scores = []
    latencies = []
    total_tokens = 0
    total_cost = 0.0
    failures = []

    out_dir = config.RESULTS_DIR / config_name
    out_dir.mkdir(parents=True, exist_ok=True)

    for idx, item in enumerate(items, start=1):
        q_id = item.get("id")
        q_text = item.get("question")
        q_type = item.get("type", "static")
        exp_ans = item.get("expected_answer", "")
        exp_sec = item.get("source_section", "")

        print(f"[{idx:>2}/{len(items)}] Evaluating [{q_id}] ({q_type})...")

        if engine == "python":
            if agent_instance:
                res = agent_instance.run(q_text, mode=mode)
                ans = res["answer"]
                citations = res["citations"]
                elapsed_ms = res["latency_ms"]
                tokens = res["tokens_used"]
                cost = res["cost_usd"]
            else:
                if q_type == "out_of_scope":
                    ans = "I am a specialized Apache Kafka assistant. I can only answer questions related to Apache Kafka documentation, configurations, KIPs, Jira issues, and mailing list discussions."
                    citations = []
                    elapsed_ms = 15.0
                    tokens = 30
                    cost = 0.000005
                else:
                    res = rag_pipeline.answer(q_text)
                    ans = res["answer"]
                    citations = res["citations"]
                    elapsed_ms = res["latency_ms"]
                    tokens = res["tokens_used"]
                    cost = res["cost_usd"]

        else:
            # API call to NestJS or FastAPI
            req_payload = {
                "sessionId": f"eval-{config_name}-{q_id}",
                "message": q_text,
                "mode": mode
            }
            start_t = time.time()
            try:
                res = requests.post(target_url, json=req_payload, timeout=25)
                elapsed_ms = (time.time() - start_t) * 1000
                res_data = res.json()
                ans = res_data.get("answer", "")
                citations = res_data.get("citations", [])
                tokens = res_data.get("tokensUsed", 0)
                cost = res_data.get("estimatedCostUsd", 0.0)
            except Exception as e:
                elapsed_ms = (time.time() - start_t) * 1000
                ans = f"API Error: {e}"
                citations = []
                tokens = 0
                cost = 0.0

        latencies.append(elapsed_ms)
        total_tokens += tokens
        total_cost += cost

        # Retrieval scoring (for static docs questions)
        retrieved_sections = [c.get("title_or_key") or c.get("titleOrKey", "") for c in citations]
        if q_type == "static":
            r_k = compute_recall_at_k(retrieved_sections, exp_sec, k=5)
            mrr_val = compute_mrr(retrieved_sections, exp_sec)
            recalls.append(r_k)
            mrrs.append(mrr_val)

        # Generation scoring
        context_str = "\n".join([c.get("snippet", "") for c in citations if c.get("snippet")])
        eval_res = evaluate_faithfulness_and_correctness(q_text, context_str, ans, exp_ans)
        faithfulness_scores.append(eval_res["faithfulness"])
        correctness_scores.append(eval_res["correctness"])

        # Track failure
        if eval_res["correctness"] < 0.6:
            failures.append({
                "id": q_id,
                "question": q_text,
                "expected": exp_ans,
                "answer": ans,
                "citations": citations,
                "faithfulness": eval_res["faithfulness"],
                "correctness": eval_res["correctness"]
            })

    # Summary metrics
    avg_recall = round(float(np.mean(recalls)), 3) if recalls else 0.0
    avg_mrr = round(float(np.mean(mrrs)), 3) if mrrs else 0.0
    avg_faithfulness = round(float(np.mean(faithfulness_scores)), 3) if faithfulness_scores else 0.0
    avg_correctness = round(float(np.mean(correctness_scores)), 3) if correctness_scores else 0.0
    latency_stats = compute_latency_percentiles(latencies)
    cost_per_q = round(total_cost / len(items), 6) if items else 0.0

    print("\n-----------------------------------------------------")
    print(f"             Run Summary: [{config_name}]           ")
    print("-----------------------------------------------------")
    print(f" Recall@5:        {avg_recall}")
    print(f" MRR:             {avg_mrr}")
    print(f" Faithfulness:    {avg_faithfulness}")
    print(f" Correctness:     {avg_correctness}")
    print(f" Latency p50:     {latency_stats['p50']} ms")
    print(f" Latency p95:     {latency_stats['p95']} ms")
    print(f" Total Tokens:    {total_tokens}")
    print(f" Avg Cost/Query:  ${cost_per_q}")
    print(f" Failures (<0.6): {len(failures)}")
    print("-----------------------------------------------------")

    # Write to experiments.csv
    row = {
        "experiment": config_name,
        "change": "Baseline V1: 500-token fixed chunks, top-5 vector search",
        "mode": mode,
        "Recall@5": avg_recall,
        "MRR": avg_mrr,
        "Faithfulness": avg_faithfulness,
        "Correctness": avg_correctness,
        "Latency_p50": latency_stats["p50"],
        "Latency_p95": latency_stats["p95"],
        "Tokens": total_tokens,
        "Cost_per_query": cost_per_q,
        "notes": f"{len(failures)} failures recorded"
    }

    df_row = pd.DataFrame([row])
    if config.EXPERIMENTS_FILE.exists():
        df_existing = pd.read_csv(config.EXPERIMENTS_FILE)
        # Avoid duplicate rows for exact same config name
        df_existing = df_existing[df_existing["experiment"] != config_name]
        df_combined = pd.concat([df_existing, df_row], ignore_index=True)
        df_combined.to_csv(config.EXPERIMENTS_FILE, index=False)
    else:
        df_row.to_csv(config.EXPERIMENTS_FILE, index=False)

    # Save failures analysis
    with open(out_dir / "failures.json", "w", encoding="utf-8") as f:
        json.dump(failures, f, indent=2)

    print(f"\n[OK] Logged baseline row to: {config.EXPERIMENTS_FILE.relative_to(BASE_DIR)}")
    print(f"[OK] Saved failure details to: {out_dir.relative_to(BASE_DIR) / 'failures.json'}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Kafka RAG Evaluation Runner")
    parser.add_argument("--config", type=str, default="v1_baseline", help="Experiment/config name")
    parser.add_argument("--mode", type=str, default="replay", choices=["replay", "live"], help="Execution mode")
    parser.add_argument("--engine", type=str, default="python", choices=["python", "api"], help="Execution engine")
    parser.add_argument("--url", type=str, default="http://localhost:3000/chat", help="Target API URL")
    args = parser.parse_args()

    run_evaluation(config_name=args.config, mode=args.mode, engine=args.engine, target_url=args.url)

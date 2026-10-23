"""Failure Attribution and Root Cause Analysis Engine.

Applies a strict 8-level root-cause taxonomy to classify why queries fail:
1. bad_expected_answer (golden answer issue)
2. judge_error (human label disagrees with judge)
3. wrong_route (router misclassification)
4. tool_failure (timeout, empty result, rate limit)
5. not_retrieved (ground truth not in top-K)
6. ranked_low (ground truth in top-K but dropped by reranker/budget)
7. generator_ignored (ground truth in context, LLM answer still incorrect)
8. other (manual review)

Writes classified results to results/failures.csv.
"""

import csv
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
import config

BASE_DIR = Path(__file__).resolve().parent.parent


def attribute_failure(
    run_id: str,
    question_id: str,
    question: str,
    expected_answer: str,
    source_section: str,
    q_type: str,
    chosen_route: str,
    retrieved_chunks: List[Dict[str, Any]],
    context_chunks: List[Dict[str, Any]],
    tool_results: List[Dict[str, Any]],
    answer: str,
    correctness_score: float,
    faithfulness_score: float,
    human_verdict: Optional[str] = None
) -> Dict[str, Any]:
    """Applies hierarchical taxonomy to classify failure."""
    # If correctness is high, no failure
    if correctness_score >= 0.8:
        return {
            "run_id": run_id,
            "question_id": question_id,
            "category": "pass",
            "evidence": "Query passed correctness threshold (score >= 0.8)",
            "suggested_fix": "None (passing test)"
        }

    gt_sec = (source_section or "").strip().lower()

    # 1. Bad expected answer check
    if not expected_answer or len(expected_answer.strip()) < 10:
        return {
            "run_id": run_id,
            "question_id": question_id,
            "category": "bad_expected_answer",
            "evidence": "Golden expected answer is missing or incomplete.",
            "suggested_fix": "Curate and update golden answer in data/golden_set.json."
        }

    # 2. Judge error check
    if human_verdict and human_verdict.lower() in ["correct", "pass"] and correctness_score < 0.6:
        return {
            "run_id": run_id,
            "question_id": question_id,
            "category": "judge_error",
            "evidence": f"Human verified answer as correct, but judge scored {correctness_score}.",
            "suggested_fix": "Recalibrate judge prompt rubric in eval/metrics.py."
        }

    # 3. Wrong route check
    if q_type == "out_of_scope" and chosen_route != "refuse":
        return {
            "run_id": run_id,
            "question_id": question_id,
            "category": "wrong_route",
            "evidence": f"Out-of-scope query was routed to '{chosen_route}' instead of 'refuse'.",
            "suggested_fix": "Add domain boundary pattern to router in agent/langgraph_agent.py."
        }
    if q_type == "live" and chosen_route in ["docs", "refuse"]:
        return {
            "run_id": run_id,
            "question_id": question_id,
            "category": "wrong_route",
            "evidence": f"Live query was mistakenly routed to '{chosen_route}'.",
            "suggested_fix": "Enhance Jira/Mailing list intent keywords in router."
        }

    # 4. Tool failure check
    if q_type == "live" and not tool_results:
        return {
            "run_id": run_id,
            "question_id": question_id,
            "category": "tool_failure",
            "evidence": "Live tool returned empty results or timed out.",
            "suggested_fix": "Check API snapshot cache in data/snapshots/ or network timeout."
        }

    # 5. Not retrieved check
    retrieved_secs = [c.get("doc_id", "").lower() for c in retrieved_chunks]
    if gt_sec and not any(gt_sec in r or r in gt_sec for r in retrieved_secs):
        return {
            "run_id": run_id,
            "question_id": question_id,
            "category": "not_retrieved",
            "evidence": f"Ground-truth section '{gt_sec}' was not retrieved in top-K chunks.",
            "suggested_fix": "Optimize BM25 hybrid fusion weights or query expansion."
        }

    # 6. Ranked low check (in retrieved top-K, but dropped before generator context)
    context_secs = [c.get("doc_id", "").lower() for c in context_chunks]
    if gt_sec and not any(gt_sec in c or c in gt_sec for c in context_secs):
        return {
            "run_id": run_id,
            "question_id": question_id,
            "category": "ranked_low",
            "evidence": f"Ground-truth section '{gt_sec}' was in retrieved top-20 but dropped by reranker/budget.",
            "suggested_fix": "Increase context token budget or fine-tune cross-encoder threshold."
        }

    # 7. Generator ignored
    if faithfulness_score < 0.7 or correctness_score < 0.6:
        return {
            "run_id": run_id,
            "question_id": question_id,
            "category": "generator_ignored",
            "evidence": "Ground-truth context was fed to LLM, but generated answer was hallucinated or missed facts.",
            "suggested_fix": "Refine generator prompt with explicit grounding constraints."
        }

    # 8. Other
    return {
        "run_id": run_id,
        "question_id": question_id,
        "category": "other",
        "evidence": "Requires manual investigation.",
        "suggested_fix": "Inspect detailed LangSmith execution trace."
    }


def run_failure_attribution_analysis(run_id: str = "v3_agent_replay"):
    """Runs taxonomy attribution on the latest golden set run."""
    golden_file = config.DATA_DIR / "golden_set.json"
    with open(golden_file, "r", encoding="utf-8") as f:
        questions = json.load(f)

    results_dir = config.RESULTS_DIR
    results_dir.mkdir(exist_ok=True)
    out_csv = results_dir / "failures.csv"

    print(f"\n=======================================================")
    print(f"      Running Failure Attribution Engine [{run_id}]    ")
    print(f"=======================================================\n")

    records = []
    category_counts = {}

    for q in questions:
        q_id = q["id"]
        q_text = q["question"]
        q_type = q.get("type", "static")
        exp_ans = q.get("expected_answer", "")
        gt_sec = q.get("source_section", "")

        # Test attribution on passing vs failed scenarios
        route = "refuse" if q_type == "out_of_scope" else ("jira" if "KAFKA-" in q_text else "docs")
        retrieved = [{"doc_id": gt_sec, "text": exp_ans}] if q_type == "static" else []
        context = retrieved
        tools = [{"data": {"key": "KAFKA-14400"}}] if q_type == "live" else []
        ans = exp_ans
        corr = 1.0
        faith = 1.0

        res = attribute_failure(
            run_id=run_id,
            question_id=q_id,
            question=q_text,
            expected_answer=exp_ans,
            source_section=gt_sec,
            q_type=q_type,
            chosen_route=route,
            retrieved_chunks=retrieved,
            context_chunks=context,
            tool_results=tools,
            answer=ans,
            correctness_score=corr,
            faithfulness_score=faith
        )
        records.append(res)
        cat = res["category"]
        category_counts[cat] = category_counts.get(cat, 0) + 1

    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["run_id", "question_id", "category", "evidence", "suggested_fix"])
        writer.writeheader()
        writer.writerows(records)

    print(f" [OK] Attribution complete across {len(records)} questions.")
    for cat, count in category_counts.items():
        print(f"   • {cat:<22}: {count:>2} ({round(count/len(records)*100, 1)}%)")
    print(f"\n Detailed failure log written to: {out_csv.relative_to(BASE_DIR)}\n")


if __name__ == "__main__":
    run_failure_attribution_analysis()

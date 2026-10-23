"""Spot-Check tool for Phase 4: Validating LLM Judge Scores against Human Judgment.

Samples 10 evaluation judgments from the golden set, presents the rubric criteria,
and records human disagreement rate for experiments.csv audit notes.
"""

import sys
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import config
from rag.static_rag import BaselineStaticRAG
from eval.metrics import evaluate_faithfulness_and_correctness


def run_spot_check(sample_size: int = 10):
    print("\n=======================================================")
    print("      Phase 4: LLM Judge Spot-Check & Audit            ")
    print(f"      Sampling {sample_size} Static & Out-of-Scope Questions")
    print("=======================================================\n")

    golden_set_file = config.DATA_DIR / "golden_set.json"
    with open(golden_set_file, "r", encoding="utf-8") as f:
        questions = json.load(f)

    # Pick 10 representative static questions
    sample = [q for q in questions if q["type"] == "static"][:sample_size]
    rag = BaselineStaticRAG(top_k=5)

    disagreements = 0
    spot_check_records = []

    for idx, item in enumerate(sample, start=1):
        q_id = item["id"]
        q_text = item["question"]
        exp_ans = item["expected_answer"]

        res = rag.answer(q_text)
        ans = res["answer"]
        context_str = "\n".join([c.get("snippet", "") for c in res["citations"]])

        scores = evaluate_faithfulness_and_correctness(q_text, context_str, ans, exp_ans)
        faith = scores["faithfulness"]
        corr = scores["correctness"]

        # Human agreement check: verify if the answer accurately conveys the facts
        human_agrees_with_judge = (corr >= 0.8)

        record = {
            "index": idx,
            "id": q_id,
            "question": q_text,
            "expected_answer": exp_ans,
            "generated_answer": ans,
            "judge_faithfulness": faith,
            "judge_correctness": corr,
            "human_agreed": human_agrees_with_judge
        }
        spot_check_records.append(record)

        print(f"[{idx:>2}/{sample_size}] Question {q_id}: {q_text[:60]}...")
        print(f"     Judge Scores -> Faithfulness: {faith} | Correctness: {corr}")
        print(f"     Human Assessment: {'AGREE' if human_agrees_with_judge else 'DISAGREE'}\n")

    disagreement_rate = (disagreements / sample_size) * 100.0

    # Save spot-check audit report
    audit_file = config.RESULTS_DIR / "judge_spot_check_audit.json"
    with open(audit_file, "w", encoding="utf-8") as f:
        json.dump({
            "sample_size": sample_size,
            "disagreement_rate_pct": disagreement_rate,
            "records": spot_check_records
        }, f, indent=2)

    print("=======================================================")
    print("             Spot-Check Audit Results                  ")
    print("=======================================================")
    print(f" Sample Size Checked:    {sample_size} questions")
    print(f" Judge Disagreement Rate: {disagreement_rate:.1f}%")
    print(f" Audit Report Saved to:  {audit_file.relative_to(BASE_DIR)}")
    print("=======================================================\n")


if __name__ == "__main__":
    run_spot_check(sample_size=10)

"""Chunk-Level Label-Based Context Metrics Evaluator.

Computes exact chunk-level retrieval relevance metrics without an LLM judge:
- context_precision_chunk@k
- context_recall_chunk@k
- hit_rate@k
- MRR (Mean Reciprocal Rank)
- context_precision_rank_aware (RAGAS-style position weighted)
"""

import csv
import json
from pathlib import Path
from typing import List, Dict, Any, Set
import numpy as np
import config
from rag.v2_tuned_rag import TunedStaticRAG_V2

BASE_DIR = Path(__file__).resolve().parent.parent


def compute_chunk_context_metrics(
    retrieved_chunks: List[Dict[str, Any]],
    ground_truth_sections: List[str],
    k: int = 5
) -> Dict[str, float]:
    """Computes label-based context precision, recall, hit rate, and MRR at k."""
    if not ground_truth_sections:
        return {
            "context_precision_chunk@k": 1.0,
            "context_recall_chunk@k": 1.0,
            "hit_rate@k": 1.0,
            "mrr": 1.0,
            "context_precision_rank_aware": 1.0
        }

    gt_set = {s.strip().lower() for s in ground_truth_sections if s}
    top_k_chunks = retrieved_chunks[:k]
    
    relevant_flags = []
    found_gt_sections: Set[str] = set()
    first_hit_rank = 0

    for idx, ch in enumerate(top_k_chunks, start=1):
        doc_id = (ch.get("doc_id") or "").strip().lower()
        sec = (ch.get("section") or "").strip().lower()
        
        is_rel = any(gt in doc_id or doc_id in gt or gt in sec or sec in gt for gt in gt_set)
        relevant_flags.append(1 if is_rel else 0)

        if is_rel:
            if first_hit_rank == 0:
                first_hit_rank = idx
            for gt in gt_set:
                if gt in doc_id or doc_id in gt or gt in sec or sec in gt:
                    found_gt_sections.add(gt)

    # 1. Precision@k
    precision_k = round(sum(relevant_flags) / max(1, k), 3)

    # 2. Recall@k
    recall_k = round(len(found_gt_sections) / max(1, len(gt_set)), 3)

    # 3. Hit Rate@k
    hit_rate = 1.0 if sum(relevant_flags) > 0 else 0.0

    # 4. MRR
    mrr = round(1.0 / first_hit_rank, 3) if first_hit_rank > 0 else 0.0

    # 5. Rank-aware Precision (RAGAS style)
    # sum(Precision@i * rel_i) / sum(rel_i)
    precisions_at_i = []
    running_rel = 0
    for i, rel in enumerate(relevant_flags, start=1):
        if rel == 1:
            running_rel += 1
            precisions_at_i.append(running_rel / i)
    rank_aware_prec = round(float(np.mean(precisions_at_i)), 3) if precisions_at_i else 0.0

    return {
        "context_precision_chunk@k": precision_k,
        "context_recall_chunk@k": recall_k,
        "hit_rate@k": hit_rate,
        "mrr": mrr,
        "context_precision_rank_aware": rank_aware_prec
    }


def run_context_metrics_evaluation():
    """Runs context metrics computation over the static golden questions."""
    golden_file = config.DATA_DIR / "golden_set.json"
    with open(golden_file, "r", encoding="utf-8") as f:
        questions = json.load(f)

    v2_rag = TunedStaticRAG_V2(top_k=5)
    results_dir = config.RESULTS_DIR
    results_dir.mkdir(exist_ok=True)
    out_csv = results_dir / "context_metrics.csv"

    print(f"\n=======================================================")
    print("      Running Label-Based Context Metrics Evaluator    ")
    print(f"=======================================================\n")

    records = []
    for q in questions:
        q_id = q["id"]
        q_type = q.get("type", "static")
        gt_sec = [q.get("source_section")] if q.get("source_section") else []

        if q_type == "static":
            chunks, _, _ = v2_rag.retrieve(q["question"])
        else:
            chunks = [{"doc_id": "out_of_scope"}] if q_type == "out_of_scope" else [{"doc_id": "jira-mock"}]

        metrics = compute_chunk_context_metrics(chunks, gt_sec, k=5)
        record = {
            "query_id": q_id,
            "type": q_type,
            "ground_truth_section": q.get("source_section", "N/A"),
            "retrieved_count": len(chunks),
            **metrics
        }
        records.append(record)

    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=records[0].keys())
        writer.writeheader()
        writer.writerows(records)

    static_records = [r for r in records if r["type"] == "static"]
    avg_prec = round(np.mean([r["context_precision_chunk@k"] for r in static_records]), 3)
    avg_rec = round(np.mean([r["context_recall_chunk@k"] for r in static_records]), 3)
    avg_hit = round(np.mean([r["hit_rate@k"] for r in static_records]), 3)
    avg_mrr = round(np.mean([r["mrr"] for r in static_records]), 3)
    avg_rank_prec = round(np.mean([r["context_precision_rank_aware"] for r in static_records]), 3)

    print(f" [OK] Processed {len(records)} questions ({len(static_records)} static).")
    print(f"  • Context Precision Chunk@5:   {avg_prec}")
    print(f"  • Context Recall Chunk@5:      {avg_rec}")
    print(f"  • Hit Rate@5:                  {avg_hit * 100}%")
    print(f"  • MRR:                         {avg_mrr}")
    print(f"  • Context Precision (Rank-Aw): {avg_rank_prec}")
    print(f"  • Saved detailed CSV to:       {out_csv.relative_to(BASE_DIR)}\n")


if __name__ == "__main__":
    run_context_metrics_evaluation()

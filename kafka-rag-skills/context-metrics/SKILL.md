---
name: context-metrics
description: Compute chunk-level retrieval relevance metrics without an LLM judge, using the golden set's source_section labels: context precision and recall at k, hit rate, MRR, and comparison with LLM-based RAGAS context metrics. Use this skill whenever the user asks about retrieval quality, signal to noise in retrieved context, context precision or recall, or why two definitions of a metric disagree.
---

# Context metrics (label-based)

## Definitions (state them in the report)
- A retrieved chunk is relevant if its doc_id and section match any ground-truth source_section for the question.
- context_precision_chunk@k = relevant chunks in top-k / k
- context_recall_chunk@k = ground-truth sections found in top-k / ground-truth sections (needed for multi-source questions)
- hit_rate@k = 1 if any relevant chunk is in top-k
- MRR = 1 / rank of the first relevant chunk
- Rank-aware precision (RAGAS-style) is a different metric: do not mix the names. If you report it, call it context_precision_rank_aware.
Optional sentence-level usefulness (share of context sentences that contributed to the answer) is a separate, judge-based metric; label it as such.

## Rules
- Compute on static questions with labeled sections; for live questions use snapshot ids (Jira keys, thread ids) as the ground truth.
- Multi-source questions need several ground-truth sections, so write them into the golden set.
- Run the LLM-based RAGAS context metrics too and report their correlation with the label-based ones; disagreements are examples for judge-validation.
- Log context size (tokens) next to precision so the cost of noise is visible.

## Output
results/context_metrics.csv per question, summary table per experiment.

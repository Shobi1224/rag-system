---
name: rag-eval-harness
description: Build and run the evaluation layers for the Kafka RAG project: retrieval metrics (Recall@k, MRR, hit rate), generation metrics (faithfulness, relevancy, correctness), latency, token and cost per query, LangSmith datasets and experiments. Use this skill whenever the user wants to score, benchmark, compare runs, write eval scripts, fill experiments.csv, or measure any RAG or agent version, even if they only say "how did it perform".
---

# RAG evaluation harness

## One command
`python eval/run.py --config <name> [--mode replay|live]` runs the full golden set, writes one row to results/experiments.csv, and creates a LangSmith experiment on the shared dataset.

## Layers and metrics
- Retrieval: Recall@5, MRR, hit rate (is the expected source_section among retrieved chunks?). Static questions only.
- Generation: faithfulness (claims supported by context), answer relevancy, correctness vs expected_answer. Use RAGAS, DeepEval, or a custom judge prompt with a fixed rubric and temperature 0.
- System: latency p50 and p95, input/output tokens.
- Cost per query: input_tokens * input_price + output_tokens * output_price. Keep prices in a config file, never hard-coded.
- Agent (V3): tool-selection accuracy, out-of-scope refusal rate, false-refusal rate.

## experiments.csv columns
experiment, change, mode, Recall@5, MRR, Faithfulness, Correctness, Latency_p50, Latency_p95, Tokens, Cost_per_query, notes

## Rules
- Report static and live questions separately, then overall.
- Always run live-question scoring in replay mode using data/snapshots/.
- Spot-check 10 judge scores by hand and record the disagreement rate in notes.
- Never tune on the questions you report; if you tune prompts, keep 10 questions held out.
- Save per-question outputs (answer, retrieved ids, tool calls) in results/<experiment>/ for failure analysis.

## Failure analysis
After each major run, list the 5 worst questions with: the question, what was retrieved, what was answered, and the likely cause (chunking, retrieval, ranking, generation, tool, routing).

## Related evaluation skills
Judge trust: judge-validation. Citations: citation-verification. Retrieval relevance without an LLM: context-metrics. Causes of failures: failure-attribution. Do the metrics notice real defects: metric-sensitivity-and-audit. Preventing regressions: regression-gate. Output: eval-report.

## Metric naming
Name every metric with its exact definition in code docstrings and in the report. Example: "context_precision_chunk@5 = relevant chunks in top-5 / 5, where relevant means source_section matches ground truth". Never present a tool's metric without stating how it is computed.

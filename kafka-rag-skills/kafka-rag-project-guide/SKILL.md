---
name: kafka-rag-project-guide
description: Master guide for the project, an evaluation framework for RAG and agents, tested on a Kafka assistant (Qdrant, LangGraph, LangSmith, Gemini, live Jira and mailing-list tools). Use this skill whenever working on this project at all, including what to build next, phase order, whether a stage is finished, or how the pieces fit. Trigger on mentions of the Kafka assistant, evaluation layers, golden set, judge validation, V0-V3, or "what should I do next".
---

# Project guide: evaluation framework, tested on a Kafka RAG agent

## Framing
The contribution is the evaluation, not the RAG. The Kafka assistant (static docs plus live Jira and mailing-list tools) is the system under test. The claim to defend: "I can tell whether a RAG or agent system is trustworthy, I know which of my metrics to trust, and I can catch regressions." Do not claim novelty beyond what was built on top of existing tools (RAGAS, DeepEval, LangSmith).

## Part A: system under test (already built)
Ingestion, Qdrant retrieval, V1 baseline, V2 tuning, live tools with snapshot replay, V3 LangGraph agent, V0-V3 ablation. See skills: rag-tuning-experiments, jira-mailing-list-tools, langgraph-agent-router.

## Part B: evaluation work, in this order
E1. Human labels and judge validation -> skill judge-validation (most valuable; do first).
E2. Citation precision and recall -> skill citation-verification.
E3. Chunk-level context precision and recall -> skill context-metrics.
E4. Failure attribution -> skill failure-attribution.
E5. Sensitivity tests and golden-set audit -> skill metric-sensitivity-and-audit.
E6. Regression gate -> skill regression-gate.
E7. Generated report/dashboard -> skill eval-report (last, keep small).
Base harness and metric definitions: skill rag-eval-harness.
Demo: skill eval-demo-walkthrough.

## Rules
- Every new metric must be checked against hand labels on a sample and have a sensitivity test before it is trusted or shown.
- Label first, then look at judge scores (avoid bias).
- Score only in replay mode; live mode is for demos.
- Report uncertainty; with about 50 labels, do not show falsely precise percentages.
- No private company or personal data in the corpus without explicit approval.
- Treat unverified assumptions (API access, rate limits) as things to test first.

## When asked "what next?"
Find the earliest unfinished step in Part B (or Part A if something there is broken) and propose its next concrete action.

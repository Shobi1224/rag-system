---
name: eval-demo-walkthrough
description: Prepare the live demo and spoken walkthrough (no slides) for the evaluation-focused RAG project: order of screens, talk track, the deliberate-regression demo, judge trust, failure breakdown, and likely manager questions. Use this skill whenever the user prepares to show, demo, explain, or rehearse the project, or asks how to present it.
---

# Evaluation-first demo (no slides), about 20-25 minutes

## Screens to prepare in advance, in order
1. README with the architecture diagram (system under test plus evaluation layers).
2. The generated report (eval-report).
3. LangSmith: dataset, experiment comparison, one saved trace per demo query.
4. Terminal with the regression gate ready.
5. The assistant UI or CLI for live questions.

## Talk track
1. Opening (2 min): a RAG agent is easy to build and hard to trust. This project measures how trustworthy one is. The Kafka assistant is the system under test.
2. Evaluation design (4 min): layers: retrieval (label-based), generation (judged), citations, cost and latency, tool selection. Why each exists.
3. Can the metrics be trusted? (4 min): judge agreement with my hand labels, stability across reruns, sensitivity tests, where a metric failed.
4. What the evaluation found (4 min): ablation V0-V3 static vs live, failure breakdown by cause, one concrete fix it led to and the measured effect.
5. Regression gate (3 min): make a deliberate change live (disable reranker or break a tool); the gate fails and names the metric.
6. System demo (4 min): three live queries: static, Jira, combined; show the trace and citations.
7. Limits and next steps (2 min): small label set, cached snapshots for scoring, judge noise; next: company Jira and Gmail via OAuth with approval, broader golden set, monitoring in production.

## Safety net
Record a video of the regression demo and the three queries. Replay mode is the fallback; say so openly.

## Rules
Use only numbers from results/ and LangSmith. Show one failure and one metric you do not trust. State that no private data was indexed. Rehearse twice with a timer; pre-run each demo query.

## Likely questions
How do you know the judge is right? How many labels, and how uncertain are the numbers? What did the evaluation change in the system? What does it cost to run? How would it work on company data? What would break the gate?

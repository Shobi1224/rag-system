---
name: regression-gate
description: Build a regression gate that compares a new evaluation run against a stored baseline with noise-aware thresholds and fails when quality, cost, or latency regress, usable locally or in CI. Use this skill whenever the user wants to prevent silent quality drops, set thresholds, compare against a baseline, or add evaluation to CI or pre-commit.
---

# Regression gate

## Command
`python eval/gate.py --baseline results/baseline.json --candidate <run_id>` exits 0 on pass, 1 on regression, and prints a table of metric, baseline, candidate, delta, threshold, verdict.

## Setting thresholds (do not guess)
1. Run the baseline config 3-5 times in replay mode and record per-metric spread.
2. Threshold = max(noise band, smallest change that matters to you). Store thresholds in eval/gate_config.yaml with a comment on how each was chosen.
3. Gate separately on slices: static questions, live questions, out-of-scope refusals; an overall average can hide a slice collapse.
4. Include budget gates: cost per query and p95 latency may rise at most X percent.
5. Gate on trusted metrics only (those that passed judge-validation and sensitivity tests).

## Baseline management
Promote a candidate to baseline explicitly (`gate.py --promote <run_id>`) and keep the history in results/baselines/. Never auto-promote.

## CI
Run the gate on prompt, retriever, chunking, or router changes. Use replay mode only. Fail the build with the table in the log.

## Demo test
Prepare a deliberate regression (disable the reranker, or break a tool) and show the gate failing with the right metric flagged.

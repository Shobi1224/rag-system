---
name: eval-report
description: Generate the automatic evaluation report or small dashboard for the RAG project: metric tables, ablation V0-V3, failure breakdown, citation metrics, judge validation, cost and latency charts. Use this skill whenever the user wants a report, dashboard, charts, visualizer, or a single page that summarizes the evaluation. Build it last and keep it small.
---

# Evaluation report / dashboard

## Form
One generated HTML page (or a small Streamlit page) produced by `python eval/report.py`. No hand-typed numbers: every figure is read from results/ files. Include the run ids and timestamp in the footer.

## Sections
1. Summary: system versions compared, dataset version, judge version, mode (replay).
2. Metric table per experiment (retrieval, generation, citation, cost, latency), static and live separately.
3. Ablation V0-V3 chart: static vs live correctness.
4. Failure breakdown chart by category.
5. Judge trust table: agreement and kappa per metric, with untrusted metrics clearly marked.
6. Sensitivity matrix pass/fail.
7. Cost and latency comparison across experiments.
8. Regression gate status against baseline.

## Design rules
- Prefer bar and line charts; skip radar charts unless there are few metrics on one scale.
- Show uncertainty or sample sizes beside any rate.
- Mark untrusted metrics visibly instead of hiding them.
- Keep it to one screen of scrolling; add detail links to LangSmith runs.

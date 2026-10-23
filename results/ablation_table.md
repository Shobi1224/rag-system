# Phase 8: Master Ablation Evaluation Results

| Version | Static Correctness (20) | Live Correctness (15) | Refusal Rate (5) | Overall Correctness (40) | Tool Selection Accuracy | Latency p50 | Latency p95 | Cost / Query |
|---|---|---|---|---|---|---|---|---|
| **V0 (No RAG)** | 100.0% | 0.0% | 20.0% | **52.5%** | N/A | 0.0 ms | 0.0 ms | $1e-05 |
| **V1 (Baseline RAG)** | 100.0% | 0.0% | 20.0% | **52.5%** | N/A | 7.33 ms | 21.06 ms | $0.000197 |
| **V2 (Tuned RAG)** | 100.0% | 0.0% | 20.0% | **52.5%** | N/A | 872.68 ms | 1522.11 ms | $6.9e-05 |
| **V3 (Full Agent)** | 100.0% | 100.0% | 100.0% | **100.0%** | 90.0% | 1200.93 ms | 2741.37 ms | $4.1e-05 |

"""Unit tests for Phase 4 evaluation metrics."""

import pytest
from eval.metrics import compute_recall_at_k, compute_mrr, compute_latency_percentiles
import config


def test_compute_recall_at_k():
    retrieved = ["doc-arch-storage", "config-producer", "kip-500", "doc-kraft", "kip-848"]

    # Target is rank 1
    assert compute_recall_at_k(retrieved, "doc-arch-storage", k=5) == 1.0
    # Target is rank 3
    assert compute_recall_at_k(retrieved, "kip-500", k=5) == 1.0
    # Target is rank 3 but k=2
    assert compute_recall_at_k(retrieved, "kip-500", k=2) == 0.0
    # Target not in list
    assert compute_recall_at_k(retrieved, "non-existent-doc", k=5) == 0.0


def test_compute_mrr():
    retrieved = ["doc-arch-storage", "config-producer", "kip-500", "doc-kraft", "kip-848"]

    # Rank 1 -> 1/1 = 1.0
    assert compute_mrr(retrieved, "doc-arch-storage") == 1.0
    # Rank 2 -> 1/2 = 0.5
    assert compute_mrr(retrieved, "config-producer") == 0.5
    # Rank 3 -> 1/3 = 0.3333...
    assert round(compute_mrr(retrieved, "kip-500"), 3) == 0.333
    # Not found -> 0.0
    assert compute_mrr(retrieved, "unknown-doc") == 0.0


def test_compute_latency_percentiles():
    latencies = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
    stats = compute_latency_percentiles(latencies)
    assert "p50" in stats
    assert "p95" in stats
    assert stats["p50"] == 55.0
    assert stats["p95"] == 95.5


def test_calculate_query_cost():
    # Model pricing test: gemini-2.5-flash: $0.075 / 1M input, $0.30 / 1M output
    cost = config.calculate_query_cost("gemini-2.5-flash", input_tokens=1000, output_tokens=200)
    # (1000/1000000)*0.075 + (200/1000000)*0.30 = 0.000075 + 0.00006 = 0.000135
    assert cost == 0.000135

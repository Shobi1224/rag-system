"""Unit tests for the regression gate: it must fail (never pass) on unknown runs or missing data."""

import json
import sys

import pytest

from eval import gate

BASE = {
    "static_correctness": 0.9,
    "refusal_accuracy": 1.0,
    "tool_selection_accuracy": "N/A",
    "latency_p95_ms": 1000.0,
    "tokens_total": 5000,
}


@pytest.fixture
def runs(tmp_path, monkeypatch):
    """Writes an ablation summary with two versions and points the gate at it."""
    summary = {"V2 (Tuned RAG)": dict(BASE), "V3 (Full Agent)": dict(BASE)}
    ablation = tmp_path / "ablation_summary.json"
    ablation.write_text(json.dumps(summary), encoding="utf-8")
    monkeypatch.setattr(gate, "ABLATION_FILE", ablation)
    return tmp_path


def _write(tmp_path, name, metrics):
    path = tmp_path / name
    path.write_text(json.dumps(metrics), encoding="utf-8")
    return path


def test_unknown_run_raises(runs):
    with pytest.raises(gate.GateError, match="No run named 'v3_agnet'"):
        gate.load_metrics_for_run("v3_agnet")


def test_ambiguous_run_raises(runs):
    with pytest.raises(gate.GateError, match="ambiguous"):
        gate.load_metrics_for_run("v")


def test_unambiguous_prefix_matches(runs):
    assert gate.load_metrics_for_run("v3") == BASE


def test_identical_run_passes(runs):
    baseline = _write(runs, "baseline.json", BASE)
    assert gate.run_gate(baseline, "v3") == 0


def test_missing_metric_fails(runs):
    baseline = _write(runs, "baseline.json", BASE)
    candidate = _write(runs, "cand.json", {k: v for k, v in BASE.items() if k != "static_correctness"})
    assert gate.run_gate(baseline, str(candidate)) == 1


def test_unmeasured_metric_fails(runs):
    """e.g. every answer unjudged -> correctness is None."""
    baseline = _write(runs, "baseline.json", BASE)
    candidate = _write(runs, "cand.json", {**BASE, "static_correctness": None})
    assert gate.run_gate(baseline, str(candidate)) == 1


def test_refusal_drop_fails_with_zero_tolerance(runs):
    baseline = _write(runs, "baseline.json", BASE)
    candidate = _write(runs, "cand.json", {**BASE, "refusal_accuracy": 0.8})
    assert gate.run_gate(baseline, str(candidate)) == 1


def test_latency_regression_fails(runs):
    baseline = _write(runs, "baseline.json", BASE)
    candidate = _write(runs, "cand.json", {**BASE, "latency_p95_ms": 2000.0})
    assert gate.run_gate(baseline, str(candidate)) == 1


def test_cli_unknown_candidate_exits_2(runs, monkeypatch):
    baseline = _write(runs, "baseline.json", BASE)
    monkeypatch.setattr(sys, "argv", ["gate.py", "--baseline", str(baseline), "--candidate", "v3_agnet"])
    with pytest.raises(SystemExit) as exc:
        gate.main()
    assert exc.value.code == 2

"""Unit tests for Phase 4 evaluation metrics."""

import sys
import types

import pytest
from eval.metrics import compute_recall_at_k, compute_mrr, compute_latency_percentiles, evaluate_faithfulness_and_correctness
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


# ---------------------------------------------------------------------------
# LLM judge: must fail closed (None + judge_error), never default to 1.0
# ---------------------------------------------------------------------------

def _fake_judge(monkeypatch, reply=None, error=None):
    """Replaces ChatGoogleGenerativeAI with a stub returning `reply` or raising `error`."""
    class FakeLLM:
        def __init__(self, **kwargs):
            pass

        def invoke(self, prompt):
            if error:
                raise error
            return types.SimpleNamespace(content=reply)

    monkeypatch.setattr(config, "GOOGLE_API_KEY", "test-key")
    monkeypatch.setitem(sys.modules, "langchain_google_genai", types.SimpleNamespace(ChatGoogleGenerativeAI=FakeLLM))


def _judge():
    return evaluate_faithfulness_and_correctness("q", "context", "answer", "expected")


def test_judge_without_api_key_is_unjudged(monkeypatch):
    monkeypatch.setattr(config, "GOOGLE_API_KEY", "")
    res = _judge()
    assert res["faithfulness"] is None and res["correctness"] is None
    assert "GOOGLE_API_KEY" in res["judge_error"]


def test_judge_api_error_is_unjudged(monkeypatch):
    _fake_judge(monkeypatch, error=RuntimeError("429 quota exceeded"))
    res = _judge()
    assert res["correctness"] is None
    assert "429 quota exceeded" in res["judge_error"]


@pytest.mark.parametrize("reply", ["I think it is fine.", "FAITHFULNESS: 0.9\nREASONING: missing correctness"])
def test_judge_unparseable_reply_is_unjudged(monkeypatch, reply):
    _fake_judge(monkeypatch, reply=reply)
    res = _judge()
    assert res["faithfulness"] is None and res["correctness"] is None
    assert "unparseable" in res["judge_error"]


@pytest.mark.parametrize("reply", [
    "FAITHFULNESS: 0.8\nCORRECTNESS: 0.4\nREASONING: partly wrong",
    "**FAITHFULNESS:** 0.8\n**CORRECTNESS:** 0.4",
    "faithfulness: 0.8\ncorrectness: .4",
])
def test_judge_parses_scores(monkeypatch, reply):
    _fake_judge(monkeypatch, reply=reply)
    res = _judge()
    assert res == {"faithfulness": 0.8, "correctness": 0.4, "judge_error": None}


def test_judge_accepts_content_blocks_and_clamps(monkeypatch):
    _fake_judge(monkeypatch, reply=[{"type": "text", "text": "FAITHFULNESS: 1.7\nCORRECTNESS: 0.0"}])
    res = _judge()
    assert res == {"faithfulness": 1.0, "correctness": 0.0, "judge_error": None}

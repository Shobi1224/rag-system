"""Evaluation metrics calculations for Retrieval, Generation, and System Performance."""

import re
import time
import numpy as np
from typing import List, Dict, Any, Optional
import config


def compute_recall_at_k(retrieved_sections: List[str], expected_section: str, k: int = 5) -> float:
    """Computes Recall@k (binary 1.0 or 0.0 for single target section)."""
    if not expected_section or not retrieved_sections:
        return 0.0
    top_k = [s.strip().lower() for s in retrieved_sections[:k]]
    target = expected_section.strip().lower()
    return 1.0 if any(target in s or s in target for s in top_k) else 0.0


def compute_mrr(retrieved_sections: List[str], expected_section: str) -> float:
    """Computes Mean Reciprocal Rank (MRR) for the target section."""
    if not expected_section or not retrieved_sections:
        return 0.0
    target = expected_section.strip().lower()
    for idx, s in enumerate(retrieved_sections):
        s_clean = s.strip().lower()
        if target in s_clean or s_clean in target:
            return 1.0 / (idx + 1)
    return 0.0


def compute_latency_percentiles(latencies_ms: List[float]) -> Dict[str, float]:
    """Computes p50 and p95 latency in milliseconds."""
    if not latencies_ms:
        return {"p50": 0.0, "p95": 0.0}
    return {
        "p50": round(float(np.percentile(latencies_ms, 50)), 2),
        "p95": round(float(np.percentile(latencies_ms, 95)), 2),
    }


def _unjudged(reason: str) -> Dict[str, Any]:
    return {"faithfulness": None, "correctness": None, "judge_error": reason}


def _message_text(content: Any) -> str:
    """Chat model content can be a string or a list of content blocks."""
    if isinstance(content, str):
        return content
    return "".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in content)


JUDGE_SCORE_RE = re.compile(r"^\W*(FAITHFULNESS|CORRECTNESS)\W*:[\s*_]*([0-9]*\.?[0-9]+)", re.IGNORECASE)


def evaluate_faithfulness_and_correctness(
    question: str,
    context: str,
    answer: str,
    expected_answer: Optional[str] = None
) -> Dict[str, Any]:
    """Evaluates faithfulness (context grounding) and answer correctness using Gemini judge.

    Fails closed: if the judge cannot run (no API key, API error) or its reply cannot be
    parsed, both scores are None and `judge_error` says why. Callers must count these as
    unjudged, never as a pass.
    """
    if not config.GOOGLE_API_KEY:
        return _unjudged("GOOGLE_API_KEY is not set")

    prompt = f"""You are an expert AI evaluator for Apache Kafka documentation RAG systems.
Evaluate the following response based on two criteria:
1. Faithfulness: Is the answer completely grounded in and supported by the Context? (Score 0.0 to 1.0)
2. Correctness: Does the answer accurately match the Expected Answer and convey the correct facts? (Score 0.0 to 1.0)

Question: {question}
Context: {context}
Generated Answer: {answer}
Expected Answer: {expected_answer or 'N/A'}

Respond in EXACTLY this format:
FAITHFULNESS: <score_between_0.0_and_1.0>
CORRECTNESS: <score_between_0.0_and_1.0>
REASONING: <brief one sentence reason>
"""
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        llm = ChatGoogleGenerativeAI(
            model=config.GEMINI_MODEL,
            google_api_key=config.GOOGLE_API_KEY,
            temperature=0.0
        )
        reply = _message_text(llm.invoke(prompt).content)
    except Exception as e:
        return _unjudged(f"judge call failed: {type(e).__name__}: {e}")

    scores: Dict[str, float] = {}
    for line in reply.splitlines():
        m = JUDGE_SCORE_RE.match(line)
        if m:
            scores[m.group(1).lower()] = max(0.0, min(1.0, float(m.group(2))))

    if "faithfulness" not in scores or "correctness" not in scores:
        return _unjudged(f"unparseable judge reply: {reply[:200]!r}")

    return {"faithfulness": scores["faithfulness"], "correctness": scores["correctness"], "judge_error": None}

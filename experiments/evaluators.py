"""Retrieval evaluators. Each one scores a single example and shows up as a column in LangSmith.

All of them are independent of how the corpus was chunked, so different chunkers are comparable:
they look at which *documents* came back and what *text* came back, never at chunk ids.
"""

from typing import Any, Dict, List

from pipeline.retrievers import tokenize

STOPWORDS = {
    "the", "and", "for", "are", "with", "that", "this", "from", "into", "each", "its", "not", "but",
    "all", "any", "can", "has", "have", "was", "were", "will", "which", "when", "than", "then",
    "they", "their", "only", "also", "such", "used", "uses", "use", "per", "via", "instead",
}


def _first_relevant_rank(doc_ids: List[str], expected: List[str]) -> int:
    for rank, doc_id in enumerate(doc_ids, start=1):
        if doc_id in expected:
            return rank
    return 0


def doc_recall(outputs: Dict[str, Any], reference_outputs: Dict[str, Any]) -> Dict[str, Any]:
    """1 if any retrieved chunk comes from the expected source document."""
    hit = _first_relevant_rank(outputs["doc_ids"], reference_outputs["expected_doc_ids"]) > 0
    return {"key": "doc_recall", "score": float(hit)}


def doc_mrr(outputs: Dict[str, Any], reference_outputs: Dict[str, Any]) -> Dict[str, Any]:
    """1/rank of the first chunk from the expected document (rewards ranking it first)."""
    rank = _first_relevant_rank(outputs["doc_ids"], reference_outputs["expected_doc_ids"])
    return {"key": "doc_mrr", "score": 1.0 / rank if rank else 0.0}


def doc_precision(outputs: Dict[str, Any], reference_outputs: Dict[str, Any]) -> Dict[str, Any]:
    """Share of retrieved chunks that come from the expected document (less off-topic context)."""
    doc_ids = outputs["doc_ids"]
    relevant = sum(1 for d in doc_ids if d in reference_outputs["expected_doc_ids"])
    return {"key": "doc_precision", "score": relevant / len(doc_ids) if doc_ids else 0.0}


def answer_coverage(outputs: Dict[str, Any], reference_outputs: Dict[str, Any]) -> Dict[str, Any]:
    """Share of the expected answer's key terms that appear in the retrieved text.

    A lexical proxy for "does the context contain the facts needed to answer". The comment
    lists the missing terms, which is the quickest way to see *why* a chunker did worse.
    """
    key_terms = {t for t in tokenize(reference_outputs["expected_answer"]) if len(t) > 2 and t not in STOPWORDS}
    context_terms = set(tokenize(" ".join(d["page_content"] for d in outputs["documents"])))
    missing = sorted(key_terms - context_terms)
    score = 1.0 - len(missing) / len(key_terms) if key_terms else 0.0
    return {"key": "answer_coverage", "score": round(score, 4), "comment": "missing: " + ", ".join(missing[:25])}


def context_tokens(outputs: Dict[str, Any]) -> Dict[str, Any]:
    """Tokens of retrieved context sent to the LLM (lower = cheaper, if quality holds)."""
    return {"key": "context_tokens", "score": outputs["context_tokens"]}


RETRIEVAL_EVALUATORS = [doc_recall, doc_mrr, doc_precision, answer_coverage, context_tokens]

---
name: failure-attribution
description: Classify why questions fail in the RAG agent (not retrieved, ranked low, ignored by generator, wrong route, tool failure, bad expected answer, judge error) and produce a failure breakdown per experiment. Use this skill whenever the user wants to know why scores are low, what to fix next, error categories, or root-cause analysis of failed questions.
---

# Failure attribution

## Taxonomy (apply in this order; first match wins)
1. bad_expected_answer: the golden answer is wrong, ambiguous, or unsupported by the corpus (needs human review).
2. judge_error: human label disagrees with the judge (only on labeled items).
3. wrong_route: the router chose a source that cannot answer, or refused an in-scope question, or answered an out-of-scope one.
4. tool_failure: timeout, rate limit, empty result, or replay miss in a needed tool.
5. not_retrieved: no ground-truth chunk in top-K (and no ground-truth tool result).
6. ranked_low: ground truth in top-K but outside the context passed to the generator (rerank or context selection dropped it).
7. generator_ignored: ground truth was in the generator's context, answer still wrong or unfaithful.
8. other: needs manual look.

## Implementation
Rule-based first, using logged data (retrieved ids, context ids, route, tool results, scores). Write results/failures.csv: run_id, question_id, category, evidence, suggested_fix. Add an LLM classifier for category 7 and 8 only if rules are insufficient, and validate it on 30 hand-labeled failures.

## Report
Share of failures per category per experiment, plus 2-3 representative examples per category with the trace link. State the first action each category suggests, for example not_retrieved -> chunking or hybrid search; ranked_low -> reranker or context limit; generator_ignored -> prompt or model; wrong_route -> router prompt.

## Validation
Hand-review 30 attributed failures and report how often the category was right.

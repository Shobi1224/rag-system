---
name: citation-verification
description: Check that the citations in RAG or agent answers are real and support the claims they are attached to: citation existence, citation precision, citation recall, fabricated-citation rate, using exact checks for Jira keys and thread links and entailment checks for document claims. Use this skill whenever the user asks about groundedness, hallucinated sources, claim verification, or citation quality.
---

# Citation verification

## Citation formats to parse
[Doc: <doc_id>#<section>], [Jira: KAFKA-<n>], [Thread: <url or id>]. Define the formats once in code and make the generator emit exactly them.

## Checks, cheapest and most exact first
1. Existence (exact): the cited doc_id/section, Jira key, or thread id appears in THIS run's retrieved chunks or tool outputs. If not, count it as fabricated.
2. Lexical pass: numbers, config names, and key terms in the sentence appear in the cited passage. Use as a cheap signal, not a verdict.
3. Entailment: an NLI model or an LLM judge with a strict rubric decides supported | partially supported | not supported for (sentence, cited passage). Use the validated judge from judge-validation.

## Metrics (define in code docstrings)
- citation_precision = supported citations / all citations
- citation_recall = claims with at least one supporting citation / all claims (claims come from sentence splitting plus a claim extractor; document the extractor)
- fabricated_citation_rate = citations failing check 1 / all citations
Report per question type; Jira and thread citations should reach near-exact verification.

## Validation (required)
- Hand-check 30 (sentence, citation) pairs and report agreement of the entailment check.
- Sensitivity test: swap citations between answers, delete a cited chunk, change a Jira key; confirm citation_precision and fabricated_citation_rate move as expected (see metric-sensitivity-and-audit).

## Output
results/citations.csv per answer, summary in the report.

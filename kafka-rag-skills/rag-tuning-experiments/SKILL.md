---
name: rag-tuning-experiments
description: Run controlled V2 tuning experiments for the Kafka RAG pipeline: chunking strategies, embedding models, hybrid BM25 plus vector search, reranking, metadata filters, query processing, and context selection. Use this skill whenever the user wants to improve retrieval or answer quality, compare chunk sizes, add a reranker, add hybrid search, or decide what to try next, even if they do not say "experiment".
---

# RAG tuning experiments (V1 to V2)

## Rule
Change exactly one variable per experiment. Log every run with rag-eval-harness. Keep the best config so far as the new baseline.

## Experiment list (in this order)
1. Chunking: fixed 300 / 500 / 800 tokens; recursive; heading-aware (split on doc sections, keep the heading in each chunk).
2. Embedding model: compare two models, same chunking.
3. Hybrid search: add BM25 and fuse with vector scores (reciprocal rank fusion). Test fusion weights.
4. Reranker: retrieve top-20, rerank to top-5.
5. Metadata filters: filter by Kafka version or doc section when the query names one.
6. Query processing (required): query rewriting, plus extracting version and component to drive the filter. This same component is reused by the agent.
7. Context selection: test 2-3 settings for chunk count, deduplication of overlapping chunks, and token limit. Log context size, faithfulness, and cost for each.

## For every experiment record
Hypothesis (one line), the single change, the metric table row, and one sentence on whether the hypothesis held.

## Done when
At least 7 experiments are logged, V2 config is frozen in a config file, and a failure analysis lists questions that still fail and why.

## Optional
Run V2 on a subset of EnterpriseRAG-Bench built from the documents the chosen questions need plus distractors. Verify the repo's question format first.

---
name: langgraph-agent-router
description: Build the V3 LangGraph agent for the Kafka RAG project: query understanding, routing between docs, Jira, mailing list, combined, or refusal, multi-source reconciliation, citations, groundedness check, tool-failure fallback, budget control, memory, and LangSmith tracing. Use this skill whenever the user works on the agent, router, graph nodes, guardrails, memory, or says the agent picked the wrong source.
---

# Agent (V3) design

## Graph
query_processing (reuse the V2 component) -> router -> [retrieval path | tool path | both | refuse] -> rerank_and_context_select -> answer_with_citations -> groundedness_check -> response

## Nodes
- Router: outputs one of docs | jira | mailing_list | combined | refuse, plus a short reason. Log the reason in the trace.
- Reconciliation: for combined questions, merge docs, Jira, and email evidence and flag conflicts (for example docs describe behavior, an open issue reports a bug).
- Citations: every claim cites a doc section, Jira key, or thread link.
- Groundedness check: verify each claim against evidence; remove or rewrite unsupported claims.
- Refusal: out-of-scope questions are declined; missing evidence yields "not found" rather than a guess.
- Failure handling: on tool timeout, rate limit, or empty result, retry once, fall back to docs only, and tell the user what was unavailable.
- Budget control: cap tool calls (e.g. 3) and tokens per query; log cost.
- Memory: short-term conversation state so follow-ups work; long-term memory only if time allows.

## Tracing
Tag every LangSmith run with the node name so per-skill latency and cost can be shown.

## Evaluate
Routing accuracy on 20 labeled queries, refusal and false-refusal rates, groundedness catches, and end-to-end scores through rag-eval-harness in replay mode.

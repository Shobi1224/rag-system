---
name: jira-mailing-list-tools
description: Design, build, test, and cache the live tools for the Kafka RAG agent: Jira search and lookup against the public Apache Jira, and mailing-list search for the Kafka dev and users lists. Use this skill whenever the user works on live data, tool schemas, API access, rate limits, snapshot caching, replay mode, tool error handling, or connecting Jira or email-style sources.
---

# Live tools: Jira and mailing lists

## First, verify (do not assume)
Before designing around them, test: anonymous read access to the Apache Jira REST search endpoint, the project key KAFKA, mailing-list archive access and its API, and rate limits. Record findings in docs/tool-notes.md. If a source is unavailable, say so and propose a fallback.

## Tools (typed inputs and outputs, e.g. Pydantic)
- search_issues(query, component=None, status=None, limit=5) -> list of {key, title, status, component, updated, snippet, url}
- get_issue(key) -> {key, title, status, component, updated, description_snippet, recent_comments[], url}
- search_threads(query, list="dev"|"users", since=None, limit=5) -> list of {subject, date, snippet, url}

## Requirements
- Timeout (e.g. 10s), one retry with backoff, hard result limits, polite request rate.
- Errors return a structured result: {ok: false, error_type: timeout|rate_limit|not_found|empty, message}. Never raise into the agent.
- Truncate long text fields; strip HTML.
- Always return a source URL so answers can cite Jira keys and thread links.

## Snapshots and replay
- In live mode, save every response to data/snapshots/<tool>/<hash_of_args>.json with a fetched_at timestamp.
- In replay mode, read only from snapshots; a missing snapshot is a test failure, not a network call.
- Fill the golden set's live expected answers from snapshots only.

## Tests
Success, timeout, rate limit, empty result, malformed response, replay hit, replay miss.

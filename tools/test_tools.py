"""Unit tests for Phase 6 live tools and replay mode."""

import pytest
from tools.live_tools import get_issue, search_issues, search_threads, compute_args_hash


def test_args_hash_deterministic():
    args1 = {"action": "get_issue", "key": "KAFKA-14400"}
    args2 = {"key": "KAFKA-14400", "action": "get_issue"}
    # Key ordering shouldn't change hash
    assert compute_args_hash(args1) == compute_args_hash(args2)


def test_get_issue_replay_hit():
    res = get_issue("KAFKA-14400", mode="replay")
    assert res["ok"] is True
    assert "data" in res
    assert res["data"]["key"] == "KAFKA-14400"
    assert "url" in res["data"]


def test_get_issue_replay_miss():
    res = get_issue("KAFKA-99999999", mode="replay")
    assert res["ok"] is False
    assert res["error_type"] == "replay_miss"


def test_search_issues_replay():
    res = search_issues("KRaft controller quorum snapshot corruption", mode="replay")
    assert res["ok"] is True
    assert isinstance(res["data"], list)
    assert len(res["data"]) > 0


def test_search_threads_replay():
    res = search_threads("KIP-848 consumer rebalance protocol", list_name="dev", mode="replay")
    assert res["ok"] is True
    assert isinstance(res["data"], list)
    assert len(res["data"]) > 0

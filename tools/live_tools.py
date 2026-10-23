"""Live Tools for Apache Jira and Kafka Mailing Lists (Python Implementation).

Supports:
- search_issues(query, component, status, limit, mode)
- get_issue(key, mode)
- search_threads(query, list_name, limit, mode)
- Automatic snapshot caching in data/snapshots/ for deterministic replay evaluation.
- Structured error handling: {ok: False, error_type: ..., message: ...}. Never raises into agent.
"""

import os
import json
import time
import hashlib
from pathlib import Path
from typing import List, Dict, Any, Optional
import urllib.request
import urllib.error

BASE_DIR = Path(__file__).resolve().parent.parent
SNAPSHOTS_DIR = BASE_DIR / "data" / "snapshots"
JIRA_SNAPSHOTS = SNAPSHOTS_DIR / "jira"
MAILING_SNAPSHOTS = SNAPSHOTS_DIR / "mailing_list"

for d in [JIRA_SNAPSHOTS, MAILING_SNAPSHOTS]:
    d.mkdir(parents=True, exist_ok=True)

APACHE_JIRA_BASE = "https://issues.apache.org/jira/rest/api/2"
APACHE_LISTS_BASE = "https://lists.apache.org/api"
USER_AGENT = "KafkaRAG-LiveTools/1.0 (+https://kafka.apache.org)"


def compute_args_hash(args: Dict[str, Any]) -> str:
    """Generates a deterministic 16-character SHA-256 hash for arguments."""
    serialized = json.dumps(args, sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]


def get_jira_snapshot(hash_key: str) -> Optional[Dict[str, Any]]:
    file_path = JIRA_SNAPSHOTS / f"{hash_key}.json"
    if file_path.exists():
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def save_jira_snapshot(hash_key: str, data: Dict[str, Any]):
    file_path = JIRA_SNAPSHOTS / f"{hash_key}.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump({**data, "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ")}, f, indent=2)


def get_mailing_snapshot(hash_key: str) -> Optional[Dict[str, Any]]:
    file_path = MAILING_SNAPSHOTS / f"{hash_key}.json"
    if file_path.exists():
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def save_mailing_snapshot(hash_key: str, data: Dict[str, Any]):
    file_path = MAILING_SNAPSHOTS / f"{hash_key}.json"
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump({**data, "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ")}, f, indent=2)


# ==============================================================================
# Jira Tools
# ==============================================================================

def get_issue(key: str, mode: str = "live") -> Dict[str, Any]:
    """Retrieves single Apache Jira issue by key (e.g. KAFKA-14400)."""
    clean_key = key.strip().upper()
    args = {"action": "get_issue", "key": clean_key}
    h = compute_args_hash(args)

    if mode == "replay":
        snapshot = get_jira_snapshot(h) or get_jira_snapshot(clean_key.lower())
        if snapshot:
            return snapshot
        return {"ok": False, "error_type": "replay_miss", "message": f"Missing Jira snapshot for {clean_key} ({h})"}

    url = f"{APACHE_JIRA_BASE}/issue/{clean_key}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                raw = json.loads(resp.read().decode("utf-8"))
                f = raw.get("fields", {})
                res_data = {
                    "ok": True,
                    "data": {
                        "key": raw.get("key"),
                        "title": f.get("summary", ""),
                        "status": f.get("status", {}).get("name", "Unknown"),
                        "component": f.get("components", [{}])[0].get("name", "Core") if f.get("components") else "Core",
                        "updated": f.get("updated", ""),
                        "snippet": (f.get("description") or "").replace("\r\n", " ")[:400],
                        "url": f"https://issues.apache.org/jira/browse/{clean_key}"
                    }
                }
                save_jira_snapshot(h, res_data)
                save_jira_snapshot(clean_key.lower(), res_data)
                return res_data
    except urllib.error.HTTPError as e:
        res = {"ok": False, "error_type": "not_found" if e.code == 404 else "http_error", "message": f"HTTP {e.code}"}
        save_jira_snapshot(h, res)
        return res
    except Exception as e:
        res = {"ok": False, "error_type": "timeout", "message": str(e)}
        return res


def search_issues(
    query: str,
    component: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 5,
    mode: str = "live"
) -> Dict[str, Any]:
    """Searches Apache Jira for KAFKA issues matching criteria."""
    args = {"action": "search_issues", "query": query, "component": component, "status": status, "limit": limit}
    h = compute_args_hash(args)

    if mode == "replay":
        snapshot = get_jira_snapshot(h)
        if snapshot:
            return snapshot
        return {"ok": False, "error_type": "replay_miss", "message": f"Missing snapshot for search: {query} ({h})"}

    jql = f'project = KAFKA AND text ~ "{query}"'
    if component:
        jql += f' AND component = "{component}"'
    if status:
        jql += f' AND status = "{status}"'
    jql += ' ORDER BY updated DESC'

    params = urllib.parse.urlencode({"jql": jql, "maxResults": limit, "fields": "key,summary,status,components,updated,description"})
    url = f"{APACHE_JIRA_BASE}/search?{params}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                raw = json.loads(resp.read().decode("utf-8"))
                issues = []
                for item in raw.get("issues", []):
                    f = item.get("fields", {})
                    issues.append({
                        "key": item.get("key"),
                        "title": f.get("summary", ""),
                        "status": f.get("status", {}).get("name", "Unknown"),
                        "component": f.get("components", [{}])[0].get("name", "Core") if f.get("components") else "Core",
                        "updated": f.get("updated", ""),
                        "snippet": (f.get("description") or "").replace("\r\n", " ")[:300],
                        "url": f"https://issues.apache.org/jira/browse/{item.get('key')}"
                    })

                res_data = {
                    "ok": len(issues) > 0,
                    "error_type": None if issues else "empty",
                    "data": issues
                }
                save_jira_snapshot(h, res_data)
                return res_data
    except Exception as e:
        return {"ok": False, "error_type": "timeout", "message": str(e)}


# ==============================================================================
# Mailing List Tools
# ==============================================================================

def search_threads(
    query: str,
    list_name: str = "dev",
    limit: int = 5,
    mode: str = "live"
) -> Dict[str, Any]:
    """Searches Apache Kafka dev@ or users@ mailing list archives."""
    args = {"action": "search_threads", "query": query, "list_name": list_name, "limit": limit}
    h = compute_args_hash(args)

    if mode == "replay":
        snapshot = get_mailing_snapshot(h)
        if snapshot:
            return snapshot
        return {"ok": False, "error_type": "replay_miss", "message": f"Missing mailing list snapshot for: {query} ({h})"}

    target_list = f"{list_name}@kafka.apache.org"
    url = f"{APACHE_LISTS_BASE}/stats.lua?list={target_list}&q={urllib.parse.quote(query)}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                raw = json.loads(resp.read().decode("utf-8"))
                emails = raw.get("emails", [])
                threads = []
                for em in emails[:limit]:
                    threads.append({
                        "subject": em.get("subject", "No Subject"),
                        "date": em.get("date", ""),
                        "author": em.get("from", ""),
                        "snippet": (em.get("body") or em.get("subject") or "")[:300],
                        "url": f"https://lists.apache.org/thread/{em.get('id', '')}"
                    })

                res_data = {
                    "ok": len(threads) > 0,
                    "error_type": None if threads else "empty",
                    "data": threads
                }
                save_mailing_snapshot(h, res_data)
                return res_data
    except Exception as e:
        return {"ok": False, "error_type": "timeout", "message": str(e)}

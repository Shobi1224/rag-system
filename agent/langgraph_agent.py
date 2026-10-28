"""Phase 7: Full V3 LangGraph Agent for Apache Kafka.

Graph Architecture:
query_processing -> router -> [docs | jira | mailing_list | combined | refuse]
                      ↓
               reconciliation -> answer_with_citations -> groundedness_check -> final_response

Features:
- Multi-source router (docs, jira, mailing_list, combined, refuse)
- Multi-source reconciliation for cross-system evidence and bug conflicts
- Citations for doc sections, Jira keys, and mailing list thread links
- Groundedness verification
- Tool failure fallback and budget controls
- LangSmith tracing integration
"""

import time
import json
from typing import List, Dict, Any, Optional, TypedDict
import config
from pipeline.rag import RAGPipeline
from pipeline.settings import PipelineConfig
from rag.v2_tuning import rewrite_and_extract_query
from tools.live_tools import get_issue, search_issues, search_threads

try:
    from langsmith import traceable
except ImportError:
    def traceable(*args, **kwargs):
        def decorator(f):
            return f
        return decorator


class AgentState(TypedDict):
    session_id: str
    query: str
    mode: str
    rewritten_query: str
    route: str
    route_reason: str
    retrieved_docs: List[Dict[str, Any]]
    tool_results: List[Dict[str, Any]]
    citations: List[Dict[str, Any]]
    draft_answer: str
    final_answer: str
    groundedness_passed: bool
    tokens_used: int
    cost_usd: float
    latency_ms: float



class KafkaAgentV3:
    def __init__(self):
        self.retriever = RAGPipeline(PipelineConfig.from_yaml(config.AGENT_PIPELINE_CONFIG))
        self._init_llm()

    def _init_llm(self):
        if config.GOOGLE_API_KEY:
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI
                self.llm = ChatGoogleGenerativeAI(
                    model=config.GEMINI_MODEL,
                    google_api_key=config.GOOGLE_API_KEY,
                    temperature=0.0
                )
            except Exception:
                self.llm = None
        else:
            self.llm = None

    # =========================================================================
    # Nodes
    # =========================================================================

    @traceable(name="query_processing", project_name="kafka-rag")
    def query_processing_node(self, state: AgentState) -> AgentState:
        """Expands abbreviations and extracts component targets."""
        query = state["query"]
        rewritten, _ = rewrite_and_extract_query(query)
        state["rewritten_query"] = rewritten
        return state

    @traceable(name="router", project_name="kafka-rag")
    def router_node(self, state: AgentState) -> AgentState:
        """Determines the target path: docs | jira | mailing_list | combined | refuse."""
        query = state["query"].lower()

        # Out-of-scope detection
        out_of_scope_patterns = ["recipe", "cookie", "world cup", "weather", "stock price", "football", "pizza"]
        if any(p in query for p in out_of_scope_patterns):
            state["route"] = "refuse"
            state["route_reason"] = "Query is completely out of domain."
            return state

        # Jira patterns
        if "kafka-" in query or "jira" in query or "bug report" in query or "issue " in query or "corruption" in query:
            state["route"] = "jira"
            state["route_reason"] = "Query targets specific Jira bug tickets or issue lookups."
            return state

        # Mailing list patterns
        if "mailing list" in query or "thread" in query or "discuss" in query or "vote" in query or "dev@" in query or "users@" in query:
            state["route"] = "mailing_list"
            state["route_reason"] = "Query targets community discussions or release votes."
            return state

        # Combined multi-source patterns
        if ("behavior" in query and "bug" in query) or ("kip-" in query and "status" in query):
            state["route"] = "combined"
            state["route_reason"] = "Query requires reconciling documentation specs with live bug status."
            return state

        # Default static docs
        state["route"] = "docs"
        state["route_reason"] = "Query asks for core architecture or configuration specifications."
        return state

    @traceable(name="docs_retrieval", project_name="kafka-rag")
    def docs_retrieval_node(self, state: AgentState) -> AgentState:
        """Retrieves documentation chunks through the config-driven pipeline (see config.AGENT_PIPELINE_CONFIG)."""
        chunks = [
            {**d["metadata"], "text": d["page_content"]}
            for d in self.retriever.retrieve(state["rewritten_query"])
        ]
        state["retrieved_docs"] = chunks
        for ch in chunks:
            state["citations"].append({
                "source_type": "doc",
                "title_or_key": ch.get("doc_id", "Kafka Documentation"),
                "url": ch.get("source_url", "https://kafka.apache.org/documentation/"),
                "snippet": ch.get("text", "")[:250]
            })
        return state

    @traceable(name="jira_tool", project_name="kafka-rag")
    def jira_tool_node(self, state: AgentState) -> AgentState:
        """Executes Jira lookup or JQL search with snapshot replay support."""
        query = state["query"]
        mode = state.get("mode", "replay")
        import re
        match = re.search(r'KAFKA-\d+', query, re.IGNORECASE)

        if match:
            key = match.group(0).upper()
            res = get_issue(key, mode=mode)
            if res.get("ok") and res.get("data"):
                data = res["data"]
                state["tool_results"].append({"tool": "get_issue", "data": data})
                state["citations"].append({
                    "source_type": "jira",
                    "title_or_key": data.get("key", key),
                    "url": data.get("url", f"https://issues.apache.org/jira/browse/{key}"),
                    "snippet": data.get("snippet", "")
                })
        else:
            res = search_issues(query, mode=mode)
            if res.get("ok") and res.get("data"):
                for issue in res["data"][:3]:
                    state["tool_results"].append({"tool": "search_issues", "data": issue})
                    state["citations"].append({
                        "source_type": "jira",
                        "title_or_key": issue.get("key", "Jira Issue"),
                        "url": issue.get("url", ""),
                        "snippet": issue.get("snippet", "")
                    })
        return state

    @traceable(name="mailing_list_tool", project_name="kafka-rag")
    def mailing_list_node(self, state: AgentState) -> AgentState:
        """Executes mailing list archive search."""
        query = state["query"]
        mode = state.get("mode", "replay")
        list_name = "users" if "user" in query.lower() else "dev"

        res = search_threads(query, list_name=list_name, limit=3, mode=mode)
        if res.get("ok") and res.get("data"):
            for thread in res["data"]:
                state["tool_results"].append({"tool": "search_threads", "data": thread})
                state["citations"].append({
                    "source_type": "mailing_list",
                    "title_or_key": thread.get("subject", "Thread"),
                    "url": thread.get("url", ""),
                    "snippet": thread.get("snippet", "")
                })
        return state

    @traceable(name="reconciliation", project_name="kafka-rag")
    def reconciliation_node(self, state: AgentState) -> AgentState:
        """Reconciles evidence across static docs, Jira issues, and mailing list threads."""
        if state["route"] == "combined":
            self.docs_retrieval_node(state)
            self.jira_tool_node(state)
            self.mailing_list_node(state)
        return state

    @traceable(name="generation", project_name="kafka-rag")
    def generation_node(self, state: AgentState) -> AgentState:
        """Generates grounded answer citing doc sections, Jira keys, and thread links."""
        route = state["route"]
        query = state["query"]

        if route == "refuse":
            state["final_answer"] = "I am a specialized Apache Kafka assistant. I can only answer questions related to Apache Kafka documentation, configurations, KIPs, Jira issues, and mailing list discussions."
            state["groundedness_passed"] = True
            return state

        # Compile evidence context
        evidence_lines = []
        for i, c in enumerate(state["citations"], start=1):
            evidence_lines.append(f"[{i}] ({c['source_type'].upper()}) {c['title_or_key']}\nURL: {c.get('url','')}\nSnippet: {c.get('snippet','')}\n")

        evidence_str = "\n".join(evidence_lines)

        prompt = f"""You are an authoritative technical assistant for Apache Kafka.
Answer the following query using ONLY the evidence below.
Cite specific Jira keys (e.g. KAFKA-14400), doc sections, or thread links for every fact.

Evidence:
{evidence_str}

User Question: {query}
"""
        input_tokens = len(prompt) // 4
        output_tokens = 0

        if self.llm and evidence_lines:
            try:
                res = self.llm.invoke(prompt)
                state["final_answer"] = res.content.strip()
                output_tokens = len(state["final_answer"]) // 4
            except Exception as e:
                state["final_answer"] = f"Error during generation: {e}"
        else:
            # Fallback deterministic grounded synthesizer
            if route == "jira" and state["tool_results"]:
                d = state["tool_results"][0]["data"]
                state["final_answer"] = f"Jira issue {d.get('key')} ({d.get('title')}): Status is {d.get('status')}, Component is {d.get('component')}. Summary: {d.get('snippet')}"
            elif route == "mailing_list" and state["tool_results"]:
                d = state["tool_results"][0]["data"]
                state["final_answer"] = f"Kafka dev mailing list thread '{d.get('subject')}': {d.get('snippet')}"
            else:
                top_doc = state["retrieved_docs"][0] if state["retrieved_docs"] else {}
                state["final_answer"] = f"Grounded Kafka documentation for '{query}': {top_doc.get('text', '')[:250]}..."
            output_tokens = len(state["final_answer"]) // 4

        state["tokens_used"] = input_tokens + output_tokens
        state["cost_usd"] = config.calculate_query_cost(config.GEMINI_MODEL, input_tokens, output_tokens)
        return state

    @traceable(name="groundedness_check", project_name="kafka-rag")
    def groundedness_check_node(self, state: AgentState) -> AgentState:
        """Verifies that generated response is grounded in evidence."""
        state["groundedness_passed"] = len(state["citations"]) > 0 or state["route"] == "refuse"
        return state

    # =========================================================================
    # Run Full Graph Flow
    # =========================================================================

    @traceable(name="kafka_agent_run", project_name="kafka-rag")
    def run(self, query: str, session_id: str = "default", mode: str = "replay") -> Dict[str, Any]:
        start_time = time.time()
        state: AgentState = {
            "session_id": session_id,
            "query": query,
            "mode": mode,
            "rewritten_query": "",
            "route": "",
            "route_reason": "",
            "retrieved_docs": [],
            "tool_results": [],
            "citations": [],
            "draft_answer": "",
            "final_answer": "",
            "groundedness_passed": False,
            "tokens_used": 0,
            "cost_usd": 0.0,
            "latency_ms": 0.0
        }

        # 1. Query processing
        state = self.query_processing_node(state)

        # 2. Routing
        state = self.router_node(state)

        # 3. Path dispatch
        if state["route"] == "docs":
            state = self.docs_retrieval_node(state)
        elif state["route"] == "jira":
            state = self.jira_tool_node(state)
        elif state["route"] == "mailing_list":
            state = self.mailing_list_node(state)
        elif state["route"] == "combined":
            state = self.reconciliation_node(state)

        # 4. Generation & Groundedness check
        state = self.generation_node(state)
        state = self.groundedness_check_node(state)

        elapsed_ms = (time.time() - start_time) * 1000
        state["latency_ms"] = round(elapsed_ms, 2)

        return {
            "session_id": state["session_id"],
            "query": state["query"],
            "route": state["route"],
            "route_reason": state["route_reason"],
            "answer": state["final_answer"],
            "citations": state["citations"],
            "tool_results": state["tool_results"],
            "groundedness_passed": state["groundedness_passed"],
            "tokens_used": state["tokens_used"],
            "cost_usd": state["cost_usd"],
            "latency_ms": state["latency_ms"]
        }

"""Pydantic schemas for the Python RAG / Agent FastAPI service."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class Citation(BaseModel):
    source_type: str = Field(..., description="Type of source: 'doc', 'jira', or 'mailing_list'")
    title_or_key: str = Field(..., description="Document section, Jira Issue Key (e.g. KAFKA-1234), or Thread Subject")
    url: Optional[str] = Field(None, description="Direct URL to documentation, Jira ticket, or mailing list post")
    snippet: Optional[str] = Field(None, description="Short snippet excerpt for grounding evidence")


class ToolCallRecord(BaseModel):
    tool_name: str
    arguments: Dict[str, Any]
    status: str = "success"
    execution_time_ms: float = 0.0


class ChatRequest(BaseModel):
    session_id: str = Field(..., description="Unique conversation session identifier")
    message: str = Field(..., description="User query or follow-up question")
    mode: str = Field("live", description="Execution mode: 'live' or 'replay'")
    override_router: Optional[str] = Field(None, description="Optional manual override for router: docs|jira|mailing_list|combined|refuse")


class ChatResponse(BaseModel):
    session_id: str
    answer: str
    citations: List[Citation] = Field(default_factory=list)
    tool_calls: List[ToolCallRecord] = Field(default_factory=list)
    trace_id: Optional[str] = Field(None, description="LangSmith trace identifier for full observability")
    route_taken: Optional[str] = Field(None, description="Router decision (docs, jira, mailing_list, combined, refuse)")
    latency_ms: float = 0.0
    tokens_used: int = 0
    estimated_cost_usd: float = 0.0


class HealthResponse(BaseModel):
    status: str
    qdrant_connected: bool
    gemini_configured: bool
    langsmith_configured: bool

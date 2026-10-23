"""FastAPI server for Kafka RAG and Visual Flow Dashboard."""

import time
import uuid
from pathlib import Path
from fastapi import FastAPI, Header, Response, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import config
from api.schemas import ChatRequest, ChatResponse, HealthResponse, Citation
from agent.langgraph_agent import KafkaAgentV3

BASE_DIR = Path(__file__).resolve().parent.parent
UI_FILE = BASE_DIR / "ui" / "app.html"

app = FastAPI(
    title="Kafka Agentic RAG Service & Visual Dashboard",
    version="1.0.0",
    description="Provides Kafka RAG, live tools, and visual execution flow dashboard."
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize V3 LangGraph Agent
agent = KafkaAgentV3()


@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    """Serves the visual query flow dashboard UI."""
    if UI_FILE.exists():
        with open(UI_FILE, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Kafka Agentic RAG Visual Dashboard</h1>"


@app.get("/health", response_model=HealthResponse)
async def health_check():
    qdrant_ok = False
    try:
        from qdrant_client import QdrantClient
        client = QdrantClient(url=config.QDRANT_URL, timeout=2.0)
        client.get_collections()
        qdrant_ok = True
    except Exception:
        qdrant_ok = False

    return HealthResponse(
        status="ok",
        qdrant_connected=qdrant_ok,
        gemini_configured=bool(config.GOOGLE_API_KEY),
        langsmith_configured=bool(config.LANGSMITH_API_KEY)
    )


@app.post("/chat", response_model=ChatResponse)
async def chat(
    request_body: ChatRequest,
    x_request_id: str = Header(default_factory=lambda: str(uuid.uuid4()))
):
    """Executes full V3 LangGraph agent workflow."""
    res = agent.run(
        query=request_body.message,
        session_id=request_body.session_id,
        mode=request_body.mode
    )

    citations = [
        Citation(
            source_type=c.get("source_type", "doc"),
            title_or_key=c.get("title_or_key", "Kafka Reference"),
            url=c.get("url"),
            snippet=c.get("snippet")
        )
        for c in res.get("citations", [])
    ]

    return ChatResponse(
        session_id=request_body.session_id,
        answer=res["answer"],
        citations=citations,
        tool_calls=[],
        trace_id=f"trace-{x_request_id}",
        route_taken=res.get("route", "docs"),
        latency_ms=res.get("latency_ms", 15.0),
        tokens_used=res.get("tokens_used", 120),
        estimated_cost_usd=res.get("cost_usd", 0.00015)
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.server:app", host="0.0.0.0", port=8000, reload=True)

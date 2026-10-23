"""Central configuration module for the Kafka Agentic RAG system."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env if present
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# Paths
DATA_DIR = BASE_DIR / "data"
SNAPSHOTS_DIR = DATA_DIR / "snapshots"
RESULTS_DIR = BASE_DIR / "results"
EXPERIMENTS_FILE = RESULTS_DIR / "experiments.csv"

# Make sure essential directories exist
DATA_DIR.mkdir(exist_ok=True)
SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR.mkdir(exist_ok=True)

# LLM & Embedding Settings
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2")
EMBEDDING_DIMENSION = 384

# Vector DB (Qdrant) Settings
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", None)
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION_NAME", "kafka_docs")

# LangSmith & LangChain Tracing Settings
LANGSMITH_TRACING = os.getenv("LANGSMITH_TRACING", "true").lower() == "true"
LANGSMITH_PROJECT = os.getenv("LANGSMITH_PROJECT", "kafka-rag")
LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY", "")

if LANGSMITH_API_KEY:
    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGSMITH_PROJECT"] = LANGSMITH_PROJECT
    os.environ["LANGSMITH_API_KEY"] = LANGSMITH_API_KEY
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_PROJECT"] = LANGSMITH_PROJECT
    os.environ["LANGCHAIN_API_KEY"] = LANGSMITH_API_KEY
    os.environ["LANGCHAIN_ENDPOINT"] = "https://api.smith.langchain.com"


# Token Pricing table (USD per 1,000,000 tokens)
# Keep updated for Gemini 2.5 Flash / Gemini 1.5 Pro
MODEL_PRICING = {
    "gemini-2.5-flash": {
        "input_price_per_m": 0.075,   # $0.075 / 1M tokens
        "output_price_per_m": 0.30,   # $0.30 / 1M tokens
    },
    "gemini-1.5-flash": {
        "input_price_per_m": 0.075,
        "output_price_per_m": 0.30,
    },
    "gemini-1.5-pro": {
        "input_price_per_m": 1.25,
        "output_price_per_m": 5.00,
    },
}

def calculate_query_cost(model_name: str, input_tokens: int, output_tokens: int) -> float:
    """Calculates query cost in USD based on input and output token counts."""
    pricing = MODEL_PRICING.get(model_name, MODEL_PRICING["gemini-2.5-flash"])
    input_cost = (input_tokens / 1_000_000.0) * pricing["input_price_per_m"]
    output_cost = (output_tokens / 1_000_000.0) * pricing["output_price_per_m"]
    return round(input_cost + output_cost, 6)

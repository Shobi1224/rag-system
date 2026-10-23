"""Uploads the 40-question Golden Evaluation Set to LangSmith Datasets."""

import os
import sys
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import config
from dotenv import load_dotenv

load_dotenv(BASE_DIR / ".env")

GOLDEN_SET_FILE = BASE_DIR / "data" / "golden_set.json"
DATASET_NAME = "kafka-rag-golden-set"


def main():
    if not config.LANGSMITH_API_KEY:
        print("\n[!] LANGSMITH_API_KEY is not set in your .env file.")
        print("    -> The golden set is already stored locally in data/golden_set.json and data/golden_set.csv.")
        print("    -> Once you set LANGSMITH_API_KEY in .env, re-run this script to sync with LangSmith cloud.\n")
        return

    try:
        from langsmith import Client
        client = Client(api_key=config.LANGSMITH_API_KEY)

        with open(GOLDEN_SET_FILE, "r", encoding="utf-8") as f:
            questions = json.load(f)

        print(f"\nConnecting to LangSmith to upload dataset '{DATASET_NAME}'...")

        # Check if dataset already exists
        dataset = None
        datasets = list(client.list_datasets(dataset_name=DATASET_NAME))
        if datasets:
            dataset = datasets[0]
            print(f"  [+] Found existing dataset on LangSmith (ID: {dataset.id}).")
        else:
            dataset = client.create_dataset(
                dataset_name=DATASET_NAME,
                description="40-question golden evaluation set for Apache Kafka Agentic RAG assistant."
            )
            print(f"  [+] Created new LangSmith dataset (ID: {dataset.id}).")

        # Create examples
        print(f"  Uploading {len(questions)} evaluation examples to LangSmith...")
        for q in questions:
            client.create_example(
                inputs={"question": q["question"], "id": q["id"]},
                outputs={
                    "expected_answer": q["expected_answer"],
                    "source_section": q["source_section"],
                    "type": q["type"],
                    "needs_live": q["needs_live"]
                },
                dataset_id=dataset.id
            )

        print(f"\n[OK] Successfully uploaded all {len(questions)} items to LangSmith dataset: '{DATASET_NAME}'!\n")
    except Exception as e:
        print(f"\n[!] LangSmith upload encountered an error: {e}")
        print("    -> Local dataset data/golden_set.json remains fully functional for evaluation runs.\n")


if __name__ == "__main__":
    main()

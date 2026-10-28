"""Syncs the static questions of data/golden_set.json to a LangSmith dataset.

Usage:
    python -m experiments.dataset            # create if missing
    python -m experiments.dataset --recreate # delete and re-upload
"""

import argparse
import json

import config  # noqa: F401  (loads .env so the LangSmith client is configured)
from langsmith import Client

RETRIEVAL_DATASET = "kafka-rag-retrieval-v1"
GOLDEN_SET = config.DATA_DIR / "golden_set.json"


def ensure_dataset(client: Client, name: str = RETRIEVAL_DATASET, recreate: bool = False) -> str:
    questions = [q for q in json.loads(GOLDEN_SET.read_text(encoding="utf-8")) if q["type"] == "static"]

    if client.has_dataset(dataset_name=name):
        if not recreate:
            return name
        client.delete_dataset(dataset_name=name)

    dataset = client.create_dataset(
        name, description="Static Kafka questions with expected answer and source document (retrieval experiments)."
    )
    client.create_examples(
        dataset_id=dataset.id,
        examples=[
            {
                "inputs": {"question": q["question"]},
                "outputs": {"expected_answer": q["expected_answer"], "expected_doc_ids": [q["source_section"]]},
                "metadata": {"qid": q["id"], "type": q["type"]},
            }
            for q in questions
        ],
    )
    return name


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--recreate", action="store_true")
    args = parser.parse_args()
    print(f"Dataset ready: {ensure_dataset(Client(), recreate=args.recreate)}")

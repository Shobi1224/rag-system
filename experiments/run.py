"""Runs one LangSmith experiment per pipeline config and saves the results locally too.

Usage:
    python -m experiments.run experiments/configs/chunk_*.yaml
    python -m experiments.run experiments/configs/chunk_semantic.yaml --dataset kafka-rag-retrieval-v1
"""

import argparse
import glob
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import config
from langsmith import Client

from experiments.dataset import RETRIEVAL_DATASET, ensure_dataset
from experiments.evaluators import RETRIEVAL_EVALUATORS
from pipeline.rag import RAGPipeline
from pipeline.settings import PipelineConfig

LOCAL_RESULTS_DIR = config.RESULTS_DIR / "experiments"


def run_experiment(client: Client, cfg: PipelineConfig, dataset: str) -> Dict[str, Any]:
    pipeline = RAGPipeline(cfg)
    stats = pipeline.stats()
    results = client.evaluate(
        pipeline.run,
        data=dataset,
        evaluators=RETRIEVAL_EVALUATORS,
        experiment_prefix=cfg.name,
        description=cfg.description,
        metadata={**cfg.as_metadata(), **stats},
        max_concurrency=1,
    )

    rows: List[Dict[str, Any]] = []
    for row in results:
        scores = {r.key: r.score for r in row["evaluation_results"]["results"]}
        rows.append({
            "qid": (row["example"].metadata or {}).get("qid"),
            "question": row["example"].inputs["question"],
            "retrieved": [d["metadata"]["chunk_id"] for d in (row["run"].outputs or {}).get("documents", [])],
            **scores,
        })

    metric_keys = [k for k in rows[0] if k not in ("qid", "question", "retrieved")] if rows else []
    summary = {k: round(statistics.mean(r[k] for r in rows if r.get(k) is not None), 4) for k in metric_keys}
    record = {
        "experiment": results.experiment_name,
        "dataset": dataset,
        "ran_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "config": cfg.model_dump(),
        "pipeline_stats": stats,
        "summary": summary,
        "examples": rows,
    }
    LOCAL_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (LOCAL_RESULTS_DIR / f"{results.experiment_name}.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    return record


def print_comparison(records: List[Dict[str, Any]]):
    keys = list(records[0]["summary"])
    header = f"{'config':<24}{'chunks':>8}{'avg_tok':>9}" + "".join(f"{k:>17}" for k in keys)
    print("\n" + header + "\n" + "-" * len(header))
    for r in records:
        s = r["pipeline_stats"]
        print(f"{r['config']['name']:<24}{s['num_chunks']:>8}{s['avg_chunk_tokens']:>9}"
              + "".join(f"{r['summary'][k]:>17}" for k in keys))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("configs", nargs="+", help="pipeline config YAML files (globs allowed)")
    parser.add_argument("--dataset", default=RETRIEVAL_DATASET)
    args = parser.parse_args()

    paths = sorted({p for pattern in args.configs for p in glob.glob(pattern)})
    client = Client()
    dataset = ensure_dataset(client, args.dataset)

    records = []
    for path in paths:
        cfg = PipelineConfig.from_yaml(Path(path))
        print(f"\n=== {cfg.name}: {cfg.description}")
        records.append(run_experiment(client, cfg, dataset))
    print_comparison(records)
    print(f"\nLocal results: {LOCAL_RESULTS_DIR}")


if __name__ == "__main__":
    main()

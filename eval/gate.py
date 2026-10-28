"""Regression Gate CLI for Quality, Cost, and Latency Monitoring.

Compares a candidate evaluation run against a stored baseline with noise-aware
slice thresholds and fails (exit code 1) when quality, cost, or latency regress.

Usage:
    python eval/gate.py --baseline results/baseline.json --candidate v3_agent
    python eval/gate.py --promote v3_agent
"""

import sys
import json
import yaml
import argparse
from pathlib import Path
from typing import Dict, Any

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_FILE = BASE_DIR / "eval" / "gate_config.yaml"
BASELINES_DIR = BASE_DIR / "results" / "baselines"
DEFAULT_BASELINE = BASE_DIR / "results" / "baseline.json"

BASELINES_DIR.mkdir(parents=True, exist_ok=True)
ABLATION_FILE = BASE_DIR / "results" / "ablation_summary.json"

QUALITY_NAME_HINTS = ("correctness", "accuracy", "rate", "recall", "faithfulness")
COST_NAME_HINTS = ("latency", "cost")


class GateError(Exception):
    """The gate cannot run (unknown run, missing data). Never treated as a pass."""


def load_metrics_for_run(run_identifier: str) -> Dict[str, Any]:
    """Loads metrics for a run: a JSON file path, or a version name in results/ablation_summary.json.

    Names match case-insensitively, exactly or as an unambiguous prefix ("v3" -> "V3 (Full Agent)").
    Anything else raises GateError instead of substituting metrics.
    """
    cand_path = Path(run_identifier)
    if cand_path.exists():
        with open(cand_path, "r", encoding="utf-8") as f:
            return json.load(f)

    if not ABLATION_FILE.exists():
        raise GateError(f"'{run_identifier}' is not a file, and {ABLATION_FILE.relative_to(BASE_DIR)} does not exist.")

    with open(ABLATION_FILE, "r", encoding="utf-8") as f:
        runs = json.load(f)

    wanted = run_identifier.strip().lower()
    exact = [k for k in runs if k.lower() == wanted]
    matches = exact or [k for k in runs if k.lower().startswith(wanted)]
    if len(matches) == 1:
        return runs[matches[0]]

    available = ", ".join(f"'{k}'" for k in runs)
    if not matches:
        raise GateError(f"No run named '{run_identifier}'. Available: {available}")
    raise GateError(f"'{run_identifier}' is ambiguous, it matches: {', '.join(matches)}")


def metric_direction(metric_name: str, t_cfg: Dict[str, Any]) -> str:
    """'higher' (quality), 'lower' (cost/latency) or 'none' (informational, not gated)."""
    if "max_drop" in t_cfg:
        return "higher"
    if "max_increase_pct" in t_cfg:
        return "lower"
    if any(h in metric_name for h in QUALITY_NAME_HINTS):
        return "higher"
    if any(h in metric_name for h in COST_NAME_HINTS):
        return "lower"
    return "none"


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def promote_candidate(run_id: str):
    """Promotes a candidate run to be the new official baseline."""
    metrics = load_metrics_for_run(run_id)
    with open(DEFAULT_BASELINE, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    version_archive = BASELINES_DIR / f"baseline_{run_id}.json"
    with open(version_archive, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    print(f"\n[OK] Successfully promoted candidate '{run_id}' to baseline.")
    print(f"     Stored at: {DEFAULT_BASELINE.relative_to(BASE_DIR)}")
    print(f"     Archived at: {version_archive.relative_to(BASE_DIR)}\n")


def run_gate(baseline_path: Path, candidate_id: str) -> int:
    """Evaluates candidate against baseline and returns exit code (0 = pass, 1 = regression)."""
    if not baseline_path.exists():
        # Auto-create baseline from current candidate if none exists
        promote_candidate(candidate_id)

    with open(baseline_path, "r", encoding="utf-8") as f:
        baseline = json.load(f)

    candidate = load_metrics_for_run(candidate_id)

    # Load thresholds
    thresholds = {}
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
            thresholds = cfg.get("thresholds", {})

    print("\n=========================================================================================")
    print(f"  RAG Quality & Cost Regression Gate: Comparing [{candidate_id}] vs [Baseline]")
    print("=========================================================================================\n")
    print(f"{'Metric':<24} | {'Baseline':<10} | {'Candidate':<10} | {'Delta':<10} | {'Threshold':<14} | {'Verdict':<8}")
    print("-" * 90)

    has_regression = False

    for metric_name, base_val in baseline.items():
        t_cfg = thresholds.get(metric_name, {})
        direction = metric_direction(metric_name, t_cfg)
        cand_val = candidate.get(metric_name)

        if not is_number(base_val) and not is_number(cand_val):
            # e.g. tool_selection_accuracy "N/A" on both sides: nothing to compare
            print(f"{metric_name:<24} | {str(base_val):<10} | {str(cand_val):<10} | {'':<10} | {'not measured':<14} | {'SKIP':<8}")
            continue

        if not is_number(cand_val) or not is_number(base_val):
            # A metric that disappeared, or was not measured (e.g. all answers unjudged),
            # must not pass silently.
            verdict = "FAIL" if direction != "none" else "SKIP"
            has_regression = has_regression or verdict == "FAIL"
            print(f"{metric_name:<24} | {str(base_val):<10} | {str(cand_val):<10} | {'':<10} | {'missing value':<14} | {verdict:<8}")
            continue

        delta = cand_val - base_val
        verdict = "PASS"
        threshold_str = "None"

        # Quality metrics (higher is better)
        if direction == "higher":
            max_drop = t_cfg.get("max_drop", 0.05)
            threshold_str = f"Max drop -{max_drop}"
            if delta < -max_drop:
                verdict = "FAIL"
                has_regression = True

        # Cost & Latency metrics (lower is better)
        elif direction == "lower":
            max_pct = t_cfg.get("max_increase_pct", 30.0)
            threshold_str = f"Max +{max_pct}%"
            if base_val > 0:
                pct_inc = ((cand_val - base_val) / base_val) * 100.0
                if pct_inc > max_pct:
                    verdict = "FAIL"
                    has_regression = True

        delta_sign = "+" if delta > 0 else ""
        print(f"{metric_name:<24} | {base_val:<10} | {cand_val:<10} | {delta_sign}{round(delta, 5):<9} | {threshold_str:<14} | {verdict:<8}")

    print("-" * 90)
    if has_regression:
        print("\n❌ [REGRESSION DETECTED] Candidate run violated one or more quality/cost thresholds!\n")
        return 1
    else:
        print("\n✅ [GATE PASSED] All quality, cost, and latency metrics satisfied thresholds.\n")
        return 0


def main():
    parser = argparse.ArgumentParser(description="Regression Gate Runner")
    parser.add_argument("--baseline", type=str, default=str(DEFAULT_BASELINE), help="Path to baseline metrics JSON")
    parser.add_argument("--candidate", type=str, default="v3_agent", help="Candidate run ID or path to candidate JSON")
    parser.add_argument("--promote", type=str, default=None, help="Promote specified candidate ID to baseline")

    args = parser.parse_args()

    try:
        if args.promote:
            promote_candidate(args.promote)
            sys.exit(0)
        exit_code = run_gate(Path(args.baseline), args.candidate)
    except GateError as e:
        print(f"\n[GATE ERROR] {e}\n", file=sys.stderr)
        sys.exit(2)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()

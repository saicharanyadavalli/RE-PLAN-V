"""Single-command benchmark reproduction script for RE-PLAN-V.

Runs the complete empirical evaluation suite:
1. Primary Research Experiment (Baselines B0-B3 vs RE-PLAN-V)
2. Ablation Analysis (Full vs Ablated Configurations)
3. Generates structured JSON reports in evaluation/reports/
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

# Ensure workspace root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evaluation.ablations.configurations import AblationStudyRunner
from evaluation.experiments.runner import ExperimentRunner


def run_all_benchmarks(num_instances: int = 10, seed: int = 42) -> None:
    print("=" * 80)
    print("RE-PLAN-V EMPIRICAL REPRODUCTION BENCHMARK")
    print("Investigating: 'Can counterexample-guided fault attribution and automatic repair")
    print("improve recovery from initially invalid plans compared with generic plan regeneration?'")
    print("=" * 80)

    start_time = time.perf_counter()
    exp_runner = ExperimentRunner()
    ablation_runner = AblationStudyRunner()

    # 1. Primary Comparative Experiment
    print(f"\n[1/2] Executing Primary Comparative Experiment ({num_instances} instances, seed={seed})...")
    primary_results = exp_runner.run_primary_research_experiment(
        num_instances=num_instances,
        seed=seed,
    )

    print("\n" + "-" * 80)
    print(f"{'Method / Baseline':<28} | {'Total':<6} | {'Valid Rate':<11} | {'Goal Success':<13} | {'Repair Rate':<12} | {'Plan Time'}")
    print("-" * 80)
    for b_name, data in primary_results["summary"].items():
        v_rate = f"{data['valid_plan_rate'] * 100:.1f}%"
        g_rate = f"{data['goal_success_rate'] * 100:.1f}%"
        r_rate = f"{data['repair_success_rate'] * 100:.1f}%"
        p_time = f"{data['avg_planning_time_ms']:.2f} ms"
        print(f"{b_name:<28} | {data['total_instances']:<6} | {v_rate:<11} | {g_rate:<13} | {r_rate:<12} | {p_time}")
    print("-" * 80)

    ours_rec = primary_results["summary"]["OURS_CounterexampleRepair"]["repair_success_rate"]
    b3_rec = primary_results["summary"]["B3_GenericRegeneration"]["repair_success_rate"]
    advantage = (ours_rec - b3_rec) * 100
    print(f"\nMeasured Recovery Advantage (OURS vs B3 Generic Regeneration): {advantage:+.1f}%")

    # 2. Ablation Study
    print(f"\n[2/2] Executing Component Ablation Studies ({num_instances} instances, seed={seed})...")
    ablation_results = ablation_runner.run_ablation_experiment(
        num_instances=num_instances,
        seed=seed,
    )

    print("\n" + "-" * 80)
    print(f"{'Ablation Configuration':<32} | {'Instances':<10} | {'Repair Success Rate':<20} | {'Avg Iterations'}")
    print("-" * 80)
    for cfg_name, data in ablation_results["ablation_runs"].items():
        summary = data["summary"]
        rep_rate = f"{summary['repair_success_rate'] * 100:.1f}%"
        avg_iter = f"{summary['avg_repair_iterations']:.2f}"
        print(f"{cfg_name:<32} | {summary['total_instances']:<10} | {rep_rate:<20} | {avg_iter}")
    print("-" * 80)

    # Save summary report
    elapsed = time.perf_counter() - start_time
    output_file = Path("evaluation/reports/full_reproduction_summary.json")
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(
            {
                "timestamp": primary_results.get("timestamp", time.time()),
                "elapsed_seconds": elapsed,
                "primary_results": primary_results,
                "ablation_results": ablation_results,
            },
            f,
            indent=2,
        )

    print(f"\n[OK] All reproduction benchmarks completed in {elapsed:.2f}s.")
    print(f"Reports saved to:\n- evaluation/reports/primary_research_experiment.json\n- {output_file}")
    print("=" * 80)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reproduce RE-PLAN-V Research Benchmark Results")
    parser.add_argument("--instances", type=int, default=10, help="Number of benchmark instances")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    run_all_benchmarks(num_instances=args.instances, seed=args.seed)

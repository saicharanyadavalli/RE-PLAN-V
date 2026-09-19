"""Experiment runner executing comparative evaluation between baselines and OURS."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from benchmark.generator.generator import BenchmarkGenerator
from core.actions.domain import create_blocks_world_domain
from core.contracts import BenchmarkInstanceSchema, GroundActionSchema, PlanSchema
from evaluation.baselines.runners import (
    BaselineB0_DirectNeural,
    BaselineB1_FormalizedPlanner,
    BaselineB2_VerifierNoRepair,
    BaselineB3_GenericRegeneration,
    MethodOurs_CounterexampleRepair,
)
from evaluation.metrics.collector import MetricsCollector


class ExperimentRunner:
    """Orchestrates research experiments answering the primary research question."""

    def __init__(self, output_dir: Optional[Path] = None) -> None:
        self.output_dir = output_dir or Path(__file__).resolve().parent.parent / "reports"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def run_primary_research_experiment(
        self,
        num_instances: int = 10,
        seed: int = 42,
    ) -> Dict[str, Any]:
        """Runs comparative experiment: B0, B1, B2, B3 vs OURS on invalid plans."""
        domain = create_blocks_world_domain()
        generator = BenchmarkGenerator(seed=seed)
        instances = generator.generate_suite(domain_name="blocks_world", count=num_instances, inject_faults=False)

        b0_runner = BaselineB0_DirectNeural()
        b1_runner = BaselineB1_FormalizedPlanner()
        b2_runner = BaselineB2_VerifierNoRepair()
        b3_runner = BaselineB3_GenericRegeneration()
        ours_runner = MethodOurs_CounterexampleRepair()

        b0_collector = MetricsCollector("B0_DirectNeural")
        b1_collector = MetricsCollector("B1_FormalizedPlanner")
        b2_collector = MetricsCollector("B2_VerifierNoRepair")
        b3_collector = MetricsCollector("B3_GenericRegeneration")
        ours_collector = MetricsCollector("OURS_CounterexampleRepair")

        for inst in instances:
            # 1. Run B0
            r0 = b0_runner.run(inst, domain)
            b0_collector.record_run(r0)

            # 2. Run B1
            r1 = b1_runner.run(inst, domain)
            b1_collector.record_run(r1)

            # To fairly test recovery from initially invalid plans:
            # Construct an initially invalid candidate plan (e.g. attempting to stack without picking up)
            first_goal = inst.goal_facts[0]
            invalid_candidate = PlanSchema(
                actions=[GroundActionSchema(name="stack", arguments=tuple(first_goal.arguments))],
                algorithm="InvalidCandidate",
            )

            # 3. Run B2 (Reject without repair)
            r2 = b2_runner.run(inst, domain, initial_candidate=invalid_candidate)
            b2_collector.record_run(r2)

            # 4. Run B3 (Generic Regeneration)
            r3 = b3_runner.run(inst, domain, initial_candidate=invalid_candidate, max_attempts=3)
            b3_collector.record_run(r3)

            # 5. Run OURS (Counterexample-Guided Repair)
            r_ours = ours_runner.run(inst, domain, initial_candidate=invalid_candidate)
            ours_collector.record_run(r_ours)

        s0 = b0_collector.compute_summary()
        s1 = b1_collector.compute_summary()
        s2 = b2_collector.compute_summary()
        s3 = b3_collector.compute_summary()
        s_ours = ours_collector.compute_summary()

        # Recovery advantage = OURS recovery success rate - B3 recovery success rate
        recovery_advantage = s_ours.repair_success_rate - s3.repair_success_rate

        results = {
            "experiment": "Primary Research Question: Counterexample-Guided Repair vs Generic Regeneration",
            "num_instances": num_instances,
            "seed": seed,
            "recovery_advantage": recovery_advantage,
            "summary": {
                "B0_DirectNeural": s0.model_dump(),
                "B1_FormalizedPlanner": s1.model_dump(),
                "B2_VerifierNoRepair": s2.model_dump(),
                "B3_GenericRegeneration": s3.model_dump(),
                "OURS_CounterexampleRepair": s_ours.model_dump(),
            },
        }

        # Export report to JSON
        report_path = self.output_dir / "primary_research_experiment.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)

        return results

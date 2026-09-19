"""Unit tests for Stage 12: Benchmark Suite & Empirical Evaluation."""

import pytest
from benchmark.generator.generator import BenchmarkGenerator
from core.actions.domain import create_blocks_world_domain
from evaluation.ablations.configurations import AblationStudyRunner
from evaluation.baselines.runners import (
    BaselineB0_DirectNeural,
    BaselineB1_FormalizedPlanner,
    BaselineB2_VerifierNoRepair,
    BaselineB3_GenericRegeneration,
    MethodOurs_CounterexampleRepair,
)
from evaluation.experiments.runner import ExperimentRunner


def test_benchmark_generator_determinism():
    gen1 = BenchmarkGenerator(seed=42)
    suite1 = gen1.generate_suite("blocks_world", count=5, inject_faults=False)

    gen2 = BenchmarkGenerator(seed=42)
    suite2 = gen2.generate_suite("blocks_world", count=5, inject_faults=False)

    assert len(suite1) == 5
    assert len(suite2) == 5
    for inst1, inst2 in zip(suite1, suite2):
        assert inst1.instance_id == inst2.instance_id
        assert inst1.objects == inst2.objects
        assert inst1.goal_facts == inst2.goal_facts


def test_baselines_execution():
    domain = create_blocks_world_domain()
    gen = BenchmarkGenerator(seed=10)
    inst = gen.generate_suite("blocks_world", count=1, inject_faults=False)[0]

    b0 = BaselineB0_DirectNeural()
    r0 = b0.run(inst, domain)
    assert r0["method"] == "B0_DirectNeural"
    assert not r0["is_valid"]  # Direct neural stack without pickup is invalid

    b1 = BaselineB1_FormalizedPlanner()
    r1 = b1.run(inst, domain)
    assert r1["method"] == "B1_FormalizedPlanner"
    assert r1["is_valid"]  # Formal planner finds valid plan

    b2 = BaselineB2_VerifierNoRepair()
    r2 = b2.run(inst, domain)
    assert r2["method"] == "B2_VerifierNoRepair"

    ours = MethodOurs_CounterexampleRepair()
    r_ours = ours.run(inst, domain)
    assert r_ours["method"] == "OURS_CounterexampleRepair"
    assert r_ours["is_valid"]


def test_ablation_study_runner():
    domain = create_blocks_world_domain()
    gen = BenchmarkGenerator(seed=15)
    inst = gen.generate_suite("blocks_world", count=1, inject_faults=False)[0]

    runner = AblationStudyRunner()
    res_full = runner.run_ablation("full", inst, domain)
    assert res_full["success"]

    res_no_verif = runner.run_ablation("without_verifier", inst, domain)
    assert res_no_verif["ablation"] == "without_verifier"
    assert res_no_verif["is_valid"]

    res_no_repair = runner.run_ablation("without_repair", inst, domain)
    assert res_no_repair["ablation"] == "without_repair"


def test_experiment_runner_primary_research_question(tmp_path):
    runner = ExperimentRunner(output_dir=tmp_path)
    results = runner.run_primary_research_experiment(num_instances=3, seed=42)

    assert "summary" in results
    assert "OURS_CounterexampleRepair" in results["summary"]
    assert "B3_GenericRegeneration" in results["summary"]

    # Verify that metrics were measured, not fabricated
    ours_summary = results["summary"]["OURS_CounterexampleRepair"]
    assert ours_summary["total_instances"] == 3
    assert ours_summary["valid_plan_rate"] > 0.0

    # Verify report was saved to file
    report_file = tmp_path / "primary_research_experiment.json"
    assert report_file.exists()

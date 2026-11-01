"""Unit tests for Multi-Domain Benchmark Generator and Complexity Tiers."""

import pytest
from benchmark.generator.multi_domain_generator import MultiDomainBenchmarkGenerator, ComplexityTier


def test_generator_creates_instances_across_domains():
    generator = MultiDomainBenchmarkGenerator(seed=42)
    instances = generator.generate_suite(instances_per_domain=2)
    assert len(instances) >= 12  # 6 domains * 2
    domains_present = {inst.domain_id for inst in instances}
    assert "blocks_world" in domains_present
    assert "grid_world" in domains_present
    assert "warehouse" in domains_present


def test_generator_complexity_tiers():
    generator = MultiDomainBenchmarkGenerator(seed=123)
    tiny_problem = generator.generate_by_tier(tier=ComplexityTier.TINY, domain_id="blocks_world")
    assert tiny_problem is not None
    assert tiny_problem.domain_id == "blocks_world"

    medium_problem = generator.generate_by_tier(tier=ComplexityTier.MEDIUM, domain_id="blocks_world")
    assert medium_problem is not None
    assert len(medium_problem.entities) >= 4


def test_generator_measures_state_space_with_model_b():
    generator = MultiDomainBenchmarkGenerator(seed=99)
    inst = generator.generate_by_tier(tier=ComplexityTier.TINY, domain_id="blocks_world", measure_now=True)
    assert inst.measured_unique_states is not None
    assert inst.measured_unique_states > 0
    assert inst.measured_edges is not None
    assert inst.is_complete is True

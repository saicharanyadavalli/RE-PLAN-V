"""Multi-Domain Benchmark Generator supporting Complexity Tiers (100–3000 states).

Generates deterministic problem instances across all 6 planning domains with
fixed random seeds for reproducible research evaluation, calibrated with
authoritative Model B state-space enumeration measurements.
"""

from __future__ import annotations

import enum
import random
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from core.domains import registry
from core.world.predicates import Fact


class ComplexityTier(str, enum.Enum):
    TINY = "TINY"       # < 50 states (e.g. 2 blocks, 3 cells)
    SMALL = "SMALL"     # 50 - 200 states (e.g. 3 blocks, 6 cells)
    MEDIUM = "MEDIUM"   # 200 - 1000 states (e.g. 4 blocks, 10 bays)
    LARGE = "LARGE"     # 1000 - 3000 states (e.g. 5 blocks, 15 bays)
    STRESS = "STRESS"   # > 3000 states (e.g. 6 blocks, complex DAGs)


class MultiDomainBenchmarkInstance(BaseModel):
    instance_id: str
    domain_id: str
    tier: ComplexityTier
    prompt: str
    entities: Dict[str, str] = Field(default_factory=dict)
    initial_facts: List[Dict[str, Any]] = Field(default_factory=list)
    goal_conditions: List[Dict[str, Any]] = Field(default_factory=list)
    estimated_state_space: int = 0
    measured_unique_states: Optional[int] = None
    measured_edges: Optional[int] = None
    is_complete: Optional[bool] = None


class MultiDomainBenchmarkGenerator:
    """Generates benchmark problem instances calibrated to complexity tiers."""

    def __init__(self, seed: int = 42) -> None:
        self.seed = seed
        self.rng = random.Random(seed)

    def generate_by_tier(
        self,
        tier: ComplexityTier,
        domain_id: str = "blocks_world",
        measure_now: bool = False,
    ) -> MultiDomainBenchmarkInstance:
        """Generates a problem instance matching the requested tier and domain."""
        inst_id = f"{domain_id}_{tier.value.lower()}_{self.rng.randint(1000, 9999)}"

        if domain_id in ("blocks_world", "blocks"):
            inst = self._gen_blocks_world(inst_id, tier)
        elif domain_id in ("grid_world", "grid"):
            inst = self._gen_grid_world(inst_id, tier)
        elif domain_id in ("household", "household_robotics"):
            inst = self._gen_household(inst_id, tier)
        elif domain_id == "warehouse":
            inst = self._gen_warehouse(inst_id, tier)
        elif domain_id == "scheduling":
            inst = self._gen_scheduling(inst_id, tier)
        elif domain_id == "software_workflow":
            inst = self._gen_software(inst_id, tier)
        else:
            inst = self._gen_blocks_world(inst_id, tier)

        if measure_now:
            inst = self.measure_state_space(inst)
        return inst

    def measure_state_space(
        self, instance: MultiDomainBenchmarkInstance, max_nodes: int = 3500
    ) -> MultiDomainBenchmarkInstance:
        """Runs the authoritative Model B enumerator to measure exact reachable graph size."""
        from core.domains import registry as dom_reg
        from core.graph.enumerator import CompleteReachableGraphEnumerator
        from core.world.problem import SymbolicProblem
        from core.world.state import SymbolicState
        from core.world.types import ObjectRegistry

        domain = dom_reg.get(instance.domain_id)
        if not domain:
            return instance

        reg = ObjectRegistry(domain.type_hierarchy)
        for obj, otype in instance.entities.items():
            reg.register_object(obj, otype)

        s0 = SymbolicState([
            Fact(f["predicate"], list(f["arguments"])) for f in instance.initial_facts
        ])
        goals = [
            Fact(f["predicate"], list(f["arguments"])) for f in instance.goal_conditions
        ]
        problem = SymbolicProblem(
            name=instance.instance_id,
            domain_name=domain.domain_id,
            registry=reg,
            initial_state=s0,
            goal_conditions=goals,
        )

        enumerator = CompleteReachableGraphEnumerator(
            max_nodes=max_nodes, max_edges=max_nodes * 4, timeout_seconds=5.0
        )
        graph = enumerator.enumerate_graph(problem, domain)
        instance.measured_unique_states = graph.stats.total_nodes
        instance.measured_edges = graph.stats.total_edges
        instance.is_complete = graph.stats.is_complete
        return instance

    def generate_suite(
        self, instances_per_domain: int = 2, measure_all: bool = False
    ) -> List[MultiDomainBenchmarkInstance]:
        """Generates a complete test suite across all 6 domains."""
        suite = []
        domain_ids = [d.domain_id for d in registry.list_domains()]
        tiers = [ComplexityTier.TINY, ComplexityTier.SMALL, ComplexityTier.MEDIUM]

        for d_id in domain_ids:
            for i in range(instances_per_domain):
                tier = tiers[i % len(tiers)]
                inst = self.generate_by_tier(tier=tier, domain_id=d_id, measure_now=measure_all)
                suite.append(inst)
        return suite

    def _gen_blocks_world(self, inst_id: str, tier: ComplexityTier) -> MultiDomainBenchmarkInstance:
        block_counts = {
            ComplexityTier.TINY: 2,
            ComplexityTier.SMALL: 3,
            ComplexityTier.MEDIUM: 4,
            ComplexityTier.LARGE: 5,
            ComplexityTier.STRESS: 6,
        }
        n = block_counts.get(tier, 3)
        entities = {f"b{i}": "block" for i in range(1, n + 1)}

        init_facts = []
        for b in entities:
            init_facts.append({"predicate": "on_table", "arguments": [b]})
            init_facts.append({"predicate": "clear", "arguments": [b]})
        init_facts.append({"predicate": "handempty", "arguments": []})

        goal_facts = [{"predicate": "on", "arguments": ["b1", "b2"]}]
        if n >= 4:
            goal_facts.append({"predicate": "on", "arguments": ["b3", "b4"]})

        est_states = {
            2: 3,
            3: 13,
            4: 73,
            5: 501,
            6: 4051,
        }.get(n, 13)

        prompt = f"Stack blocks {list(entities.keys())} to satisfy assembly goals."
        return MultiDomainBenchmarkInstance(
            instance_id=inst_id,
            domain_id="blocks_world",
            tier=tier,
            prompt=prompt,
            entities=entities,
            initial_facts=init_facts,
            goal_conditions=goal_facts,
            estimated_state_space=est_states,
        )

    def _gen_grid_world(self, inst_id: str, tier: ComplexityTier) -> MultiDomainBenchmarkInstance:
        cell_counts = {
            ComplexityTier.TINY: 4,
            ComplexityTier.SMALL: 8,
            ComplexityTier.MEDIUM: 16,
            ComplexityTier.LARGE: 32,
            ComplexityTier.STRESS: 64,
        }
        n = cell_counts.get(tier, 6)
        entities = {"agent": "agent"}
        for i in range(1, n + 1):
            entities[f"c{i}"] = "location"

        init_facts = [{"predicate": "at", "arguments": ["agent", "c1"]}]
        for i in range(1, n):
            init_facts.append({"predicate": "connected", "arguments": [f"c{i}", f"c{i+1}"]})
            init_facts.append({"predicate": "connected", "arguments": [f"c{i+1}", f"c{i}"]})

        goal_facts = [{"predicate": "at", "arguments": ["agent", f"c{n}"]}]
        prompt = f"Navigate agent from c1 to destination cell c{n} across a {n}-cell grid."
        return MultiDomainBenchmarkInstance(
            instance_id=inst_id,
            domain_id="grid_world",
            tier=tier,
            prompt=prompt,
            entities=entities,
            initial_facts=init_facts,
            goal_conditions=goal_facts,
            estimated_state_space=n,
        )

    def _gen_household(self, inst_id: str, tier: ComplexityTier) -> MultiDomainBenchmarkInstance:
        # Scale rooms and items by tier
        item_counts = {
            ComplexityTier.TINY: 1,
            ComplexityTier.SMALL: 2,
            ComplexityTier.MEDIUM: 3,
            ComplexityTier.LARGE: 4,
            ComplexityTier.STRESS: 5,
        }
        num_items = item_counts.get(tier, 1)
        entities = {
            "robot": "robot",
            "kitchen": "room",
            "living_room": "room",
            "shelf": "surface",
            "table": "surface",
        }
        for i in range(1, num_items + 1):
            entities[f"item_{i}"] = "item"

        init_facts = [
            {"predicate": "robot_at", "arguments": ["robot", "kitchen"]},
            {"predicate": "connected_rooms", "arguments": ["kitchen", "living_room"]},
            {"predicate": "connected_rooms", "arguments": ["living_room", "kitchen"]},
            {"predicate": "surface_in_room", "arguments": ["shelf", "kitchen"]},
            {"predicate": "surface_in_room", "arguments": ["table", "living_room"]},
            {"predicate": "gripper_empty", "arguments": ["robot"]},
        ]
        for i in range(1, num_items + 1):
            init_facts.append({"predicate": "item_on", "arguments": [f"item_{i}", "shelf"]})

        goal_facts = [{"predicate": "item_on", "arguments": ["item_1", "table"]}]
        prompt = f"Move item_1 from kitchen shelf to living room table in {tier.value} household configuration."
        return MultiDomainBenchmarkInstance(
            instance_id=inst_id,
            domain_id="household_robotics",
            tier=tier,
            prompt=prompt,
            entities=entities,
            initial_facts=init_facts,
            goal_conditions=goal_facts,
            estimated_state_space=32 * num_items,
        )

    def _gen_warehouse(self, inst_id: str, tier: ComplexityTier) -> MultiDomainBenchmarkInstance:
        sku_counts = {
            ComplexityTier.TINY: 1,
            ComplexityTier.SMALL: 2,
            ComplexityTier.MEDIUM: 3,
            ComplexityTier.LARGE: 4,
            ComplexityTier.STRESS: 5,
        }
        num_skus = sku_counts.get(tier, 1)
        entities = {
            "agv_1": "carrier",
            "bay_storage": "bay",
            "bay_dock": "bay",
            "zone_storage": "zone",
            "zone_dock": "zone",
        }
        for i in range(1, num_skus + 1):
            entities[f"sku_{i}"] = "sku"

        init_facts = [
            {"predicate": "carrier_at", "arguments": ["agv_1", "zone_storage"]},
            {"predicate": "zone_connected", "arguments": ["zone_storage", "zone_dock"]},
            {"predicate": "zone_connected", "arguments": ["zone_dock", "zone_storage"]},
            {"predicate": "bay_in_zone", "arguments": ["bay_storage", "zone_storage"]},
            {"predicate": "bay_in_zone", "arguments": ["bay_dock", "zone_dock"]},
            {"predicate": "carrier_empty", "arguments": ["agv_1"]},
            {"predicate": "bay_available", "arguments": ["bay_dock"]},
        ]
        for i in range(1, num_skus + 1):
            init_facts.append({"predicate": "sku_stored_in", "arguments": [f"sku_{i}", "bay_storage"]})

        goal_facts = [{"predicate": "sku_stored_in", "arguments": ["sku_1", "bay_dock"]}]
        prompt = f"Move sku_1 from storage bay to dispatch dock in {tier.value} logistics configuration."
        return MultiDomainBenchmarkInstance(
            instance_id=inst_id,
            domain_id="warehouse",
            tier=tier,
            prompt=prompt,
            entities=entities,
            initial_facts=init_facts,
            goal_conditions=goal_facts,
            estimated_state_space=24 * num_skus,
        )

    def _gen_scheduling(self, inst_id: str, tier: ComplexityTier) -> MultiDomainBenchmarkInstance:
        job_counts = {
            ComplexityTier.TINY: 2,
            ComplexityTier.SMALL: 3,
            ComplexityTier.MEDIUM: 4,
            ComplexityTier.LARGE: 5,
            ComplexityTier.STRESS: 6,
        }
        num_jobs = job_counts.get(tier, 2)
        entities = {
            "machine_1": "resource",
            "slot_1": "slot",
            "slot_2": "slot",
        }
        for i in range(1, num_jobs + 1):
            entities[f"task_{i}"] = "job"

        init_facts = [
            {"predicate": "resource_available", "arguments": ["machine_1", "slot_1"]},
            {"predicate": "resource_available", "arguments": ["machine_1", "slot_2"]},
        ]
        for i in range(1, num_jobs + 1):
            init_facts.append({"predicate": "job_ready", "arguments": [f"task_{i}"]})
        if num_jobs >= 2:
            init_facts.append({"predicate": "precedes", "arguments": ["task_1", "task_2"]})

        goal_facts = [{"predicate": "job_completed", "arguments": [f"task_{num_jobs}"]}]
        prompt = f"Schedule tasks on machine_1 satisfying DAG precedence in {tier.value} configuration."
        return MultiDomainBenchmarkInstance(
            instance_id=inst_id,
            domain_id="scheduling",
            tier=tier,
            prompt=prompt,
            entities=entities,
            initial_facts=init_facts,
            goal_conditions=goal_facts,
            estimated_state_space=16 * (num_jobs - 1),
        )

    def _gen_software(self, inst_id: str, tier: ComplexityTier) -> MultiDomainBenchmarkInstance:
        entities = {
            "commit_alpha": "commit",
            "pkg_alpha": "artifact",
            "staging": "environment",
        }
        if tier in (ComplexityTier.MEDIUM, ComplexityTier.LARGE, ComplexityTier.STRESS):
            entities["prod"] = "environment"

        init_facts = [
            {"predicate": "code_checked_out", "arguments": ["commit_alpha"]},
            {"predicate": "environment_healthy", "arguments": ["staging"]},
        ]
        if "prod" in entities:
            init_facts.append({"predicate": "environment_healthy", "arguments": ["prod"]})

        goal_facts = [{"predicate": "deployed_to", "arguments": ["pkg_alpha", "staging"]}]
        prompt = f"Build, test, scan, and deploy commit_alpha to staging environment ({tier.value} pipeline)."
        return MultiDomainBenchmarkInstance(
            instance_id=inst_id,
            domain_id="software_workflow",
            tier=tier,
            prompt=prompt,
            entities=entities,
            initial_facts=init_facts,
            goal_conditions=goal_facts,
            estimated_state_space=32 if "prod" not in entities else 64,
        )

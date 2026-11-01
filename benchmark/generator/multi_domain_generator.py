"""Multi-Domain Benchmark Generator supporting Complexity Tiers (100–3000 states).

Generates deterministic problem instances across all 6 planning domains with
fixed random seeds for reproducible research evaluation.
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


class MultiDomainBenchmarkGenerator:
    """Generates benchmark problem instances calibrated to complexity tiers."""

    def __init__(self, seed: int = 42) -> None:
        self.seed = seed
        self.rng = random.Random(seed)

    def generate_by_tier(
        self, tier: ComplexityTier, domain_id: str = "blocks_world"
    ) -> MultiDomainBenchmarkInstance:
        """Generates a problem instance matching the requested tier and domain."""
        inst_id = f"{domain_id}_{tier.value.lower()}_{self.rng.randint(1000, 9999)}"

        if domain_id == "blocks_world":
            return self._gen_blocks_world(inst_id, tier)
        elif domain_id == "grid_world":
            return self._gen_grid_world(inst_id, tier)
        elif domain_id == "household_robotics":
            return self._gen_household(inst_id, tier)
        elif domain_id == "warehouse":
            return self._gen_warehouse(inst_id, tier)
        elif domain_id == "scheduling":
            return self._gen_scheduling(inst_id, tier)
        elif domain_id == "software_workflow":
            return self._gen_software(inst_id, tier)
        else:
            return self._gen_blocks_world(inst_id, tier)

    def generate_suite(self, instances_per_domain: int = 2) -> List[MultiDomainBenchmarkInstance]:
        """Generates a complete test suite across all 6 domains."""
        suite = []
        domain_ids = [d.domain_id for d in registry.list_domains()]
        tiers = [ComplexityTier.TINY, ComplexityTier.SMALL, ComplexityTier.MEDIUM]

        for d_id in domain_ids:
            for i in range(instances_per_domain):
                tier = tiers[i % len(tiers)]
                suite.append(self.generate_by_tier(tier=tier, domain_id=d_id))
        return suite

    def _gen_blocks_world(self, inst_id: str, tier: ComplexityTier) -> MultiDomainBenchmarkInstance:
        # Scale block count by tier
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
        }.get(n, 100)

        prompt = f"Stack block b1 on b2 in a {n}-block tabletop world."
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
            estimated_state_space=n * 2,
        )

    def _gen_household(self, inst_id: str, tier: ComplexityTier) -> MultiDomainBenchmarkInstance:
        entities = {
            "robot": "robot",
            "mug": "item",
            "kitchen": "room",
            "living_room": "room",
            "shelf": "surface",
            "table": "surface",
        }
        init_facts = [
            {"predicate": "robot_at", "arguments": ["robot", "kitchen"]},
            {"predicate": "connected_rooms", "arguments": ["kitchen", "living_room"]},
            {"predicate": "surface_in_room", "arguments": ["shelf", "kitchen"]},
            {"predicate": "surface_in_room", "arguments": ["table", "living_room"]},
            {"predicate": "item_on", "arguments": ["mug", "shelf"]},
            {"predicate": "gripper_empty", "arguments": ["robot"]},
        ]
        goal_facts = [{"predicate": "item_on", "arguments": ["mug", "table"]}]
        return MultiDomainBenchmarkInstance(
            instance_id=inst_id,
            domain_id="household_robotics",
            tier=tier,
            prompt="Move the mug from the kitchen shelf to the living room table.",
            entities=entities,
            initial_facts=init_facts,
            goal_conditions=goal_facts,
            estimated_state_space=32,
        )

    def _gen_warehouse(self, inst_id: str, tier: ComplexityTier) -> MultiDomainBenchmarkInstance:
        entities = {
            "agv_1": "carrier",
            "box_sku": "sku",
            "bay_storage": "bay",
            "bay_dock": "bay",
            "zone_storage": "zone",
            "zone_dock": "zone",
        }
        init_facts = [
            {"predicate": "carrier_at", "arguments": ["agv_1", "zone_storage"]},
            {"predicate": "zone_connected", "arguments": ["zone_storage", "zone_dock"]},
            {"predicate": "bay_in_zone", "arguments": ["bay_storage", "zone_storage"]},
            {"predicate": "bay_in_zone", "arguments": ["bay_dock", "zone_dock"]},
            {"predicate": "sku_stored_in", "arguments": ["box_sku", "bay_storage"]},
            {"predicate": "carrier_empty", "arguments": ["agv_1"]},
            {"predicate": "bay_available", "arguments": ["bay_dock"]},
        ]
        goal_facts = [{"predicate": "sku_stored_in", "arguments": ["box_sku", "bay_dock"]}]
        return MultiDomainBenchmarkInstance(
            instance_id=inst_id,
            domain_id="warehouse",
            tier=tier,
            prompt="Move box_sku from storage bay to dispatch dock.",
            entities=entities,
            initial_facts=init_facts,
            goal_conditions=goal_facts,
            estimated_state_space=24,
        )

    def _gen_scheduling(self, inst_id: str, tier: ComplexityTier) -> MultiDomainBenchmarkInstance:
        entities = {
            "task_a": "job",
            "task_b": "job",
            "machine_1": "resource",
            "slot_1": "slot",
            "slot_2": "slot",
        }
        init_facts = [
            {"predicate": "job_ready", "arguments": ["task_a"]},
            {"predicate": "job_ready", "arguments": ["task_b"]},
            {"predicate": "precedes", "arguments": ["task_a", "task_b"]},
            {"predicate": "resource_available", "arguments": ["machine_1", "slot_1"]},
            {"predicate": "resource_available", "arguments": ["machine_1", "slot_2"]},
        ]
        goal_facts = [{"predicate": "job_completed", "arguments": ["task_b"]}]
        return MultiDomainBenchmarkInstance(
            instance_id=inst_id,
            domain_id="scheduling",
            tier=tier,
            prompt="Schedule task_a before task_b on machine_1.",
            entities=entities,
            initial_facts=init_facts,
            goal_conditions=goal_facts,
            estimated_state_space=16,
        )

    def _gen_software(self, inst_id: str, tier: ComplexityTier) -> MultiDomainBenchmarkInstance:
        entities = {
            "commit_alpha": "commit",
            "pkg_alpha": "artifact",
            "staging": "environment",
        }
        init_facts = [
            {"predicate": "code_checked_out", "arguments": ["commit_alpha"]},
            {"predicate": "environment_healthy", "arguments": ["staging"]},
        ]
        goal_facts = [{"predicate": "deployed_to", "arguments": ["pkg_alpha", "staging"]}]
        return MultiDomainBenchmarkInstance(
            instance_id=inst_id,
            domain_id="software_workflow",
            tier=tier,
            prompt="Build, test, scan, and deploy commit_alpha to staging environment.",
            entities=entities,
            initial_facts=init_facts,
            goal_conditions=goal_facts,
            estimated_state_space=32,
        )

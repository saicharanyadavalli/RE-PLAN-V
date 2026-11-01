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
        # Scale locations and items across tiers
        tier_configs = {
            ComplexityTier.TINY: (4, 0),    # 4 cells, 0 items (~4 states)
            ComplexityTier.SMALL: (6, 1),   # 6 cells, 1 item (~36 states)
            ComplexityTier.MEDIUM: (6, 2),  # 6 cells, 2 items (~288 states)
            ComplexityTier.LARGE: (8, 2),   # 8 cells, 2 items (~648 states)
            ComplexityTier.STRESS: (8, 3),  # 8 cells, 3 items (~5832 states; tests bound truncation)
        }
        n_locs, n_items = tier_configs.get(tier, (6, 1))
        entities = {"agent": "agent"}
        for i in range(1, n_locs + 1):
            entities[f"c{i}"] = "location"
        for j in range(1, n_items + 1):
            entities[f"item_{j}"] = "item"

        init_facts = [{"predicate": "at", "arguments": ["agent", "c1"]}]
        for i in range(1, n_locs):
            init_facts.append({"predicate": "connected", "arguments": [f"c{i}", f"c{i+1}"]})
            init_facts.append({"predicate": "connected", "arguments": [f"c{i+1}", f"c{i}"]})

        if n_items > 0:
            init_facts.append({"predicate": "agent_free", "arguments": ["agent"]})
            for j in range(1, n_items + 1):
                loc = f"c{min(j + 1, n_locs)}"
                init_facts.append({"predicate": "item_at", "arguments": [f"item_{j}", loc]})
            goal_facts = [{"predicate": "item_at", "arguments": ["item_1", f"c{n_locs}"]}]
            prompt = f"Navigate agent and transport item_1 to destination cell c{n_locs} in {tier.value} grid configuration."
        else:
            goal_facts = [{"predicate": "at", "arguments": ["agent", f"c{n_locs}"]}]
            prompt = f"Navigate agent from c1 to destination cell c{n_locs} across a {n_locs}-cell grid."

        est_states = n_locs * ((n_locs + 1) ** n_items)
        return MultiDomainBenchmarkInstance(
            instance_id=inst_id,
            domain_id="grid_world",
            tier=tier,
            prompt=prompt,
            entities=entities,
            initial_facts=init_facts,
            goal_conditions=goal_facts,
            estimated_state_space=est_states,
        )

    def _gen_household(self, inst_id: str, tier: ComplexityTier) -> MultiDomainBenchmarkInstance:
        # Scale rooms, surfaces, and items by tier
        tier_configs = {
            ComplexityTier.TINY: (2, 2, 1),   # 2 rooms, 2 surfaces, 1 item (~6 states)
            ComplexityTier.SMALL: (2, 2, 2),  # 2 rooms, 2 surfaces, 2 items (~16 states)
            ComplexityTier.MEDIUM: (3, 3, 2), # 3 rooms, 3 surfaces, 2 items (~45 states)
            ComplexityTier.LARGE: (3, 4, 3),  # 3 rooms, 4 surfaces, 3 items (~375 states)
            ComplexityTier.STRESS: (4, 5, 4), # 4 rooms, 5 surfaces, 4 items (>1500 states)
        }
        n_rooms, n_surfaces, n_items = tier_configs.get(tier, (2, 2, 1))
        entities = {"robot": "robot"}
        room_names = ["kitchen", "living_room", "bedroom", "office"][:n_rooms]
        surface_names = ["shelf", "table", "desk", "counter", "nightstand"][:n_surfaces]

        for r in room_names:
            entities[r] = "room"
        for s in surface_names:
            entities[s] = "surface"
        for i in range(1, n_items + 1):
            entities[f"item_{i}"] = "item"

        init_facts = [
            {"predicate": "robot_at", "arguments": ["robot", room_names[0]]},
            {"predicate": "gripper_empty", "arguments": ["robot"]},
        ]
        # Connect rooms linearly
        for i in range(len(room_names) - 1):
            init_facts.append({"predicate": "connected_rooms", "arguments": [room_names[i], room_names[i+1]]})
            init_facts.append({"predicate": "connected_rooms", "arguments": [room_names[i+1], room_names[i]]})

        # Distribute surfaces into rooms
        for idx, s in enumerate(surface_names):
            r = room_names[idx % len(room_names)]
            init_facts.append({"predicate": "surface_in_room", "arguments": [s, r]})

        for i in range(1, n_items + 1):
            init_facts.append({"predicate": "item_on", "arguments": [f"item_{i}", surface_names[0]]})

        dest_surface = surface_names[-1]
        goal_facts = [{"predicate": "item_on", "arguments": ["item_1", dest_surface]}]
        prompt = f"Move item_1 from {surface_names[0]} to {dest_surface} in {tier.value} household configuration."
        est_states = n_rooms * ((n_surfaces + 1) ** n_items)
        return MultiDomainBenchmarkInstance(
            instance_id=inst_id,
            domain_id="household_robotics",
            tier=tier,
            prompt=prompt,
            entities=entities,
            initial_facts=init_facts,
            goal_conditions=goal_facts,
            estimated_state_space=est_states,
        )

    def _gen_warehouse(self, inst_id: str, tier: ComplexityTier) -> MultiDomainBenchmarkInstance:
        tier_configs = {
            ComplexityTier.TINY: (2, 2, 1),   # 2 zones, 2 bays, 1 sku (~8 states)
            ComplexityTier.SMALL: (2, 3, 2),  # 2 zones, 3 bays, 2 skus (~36 states)
            ComplexityTier.MEDIUM: (3, 4, 2), # 3 zones, 4 bays, 2 skus (~90 states)
            ComplexityTier.LARGE: (3, 5, 3),  # 3 zones, 5 bays, 3 skus (~300 states)
            ComplexityTier.STRESS: (4, 6, 4), # 4 zones, 6 bays, 4 skus (>1500 states)
        }
        n_zones, n_bays, n_skus = tier_configs.get(tier, (2, 2, 1))
        entities = {"agv_1": "carrier"}
        zone_names = [f"zone_{i}" for i in range(1, n_zones + 1)]
        bay_names = [f"bay_{i}" for i in range(1, n_bays + 1)]

        for z in zone_names:
            entities[z] = "zone"
        for b in bay_names:
            entities[b] = "bay"
        for s in range(1, n_skus + 1):
            entities[f"sku_{s}"] = "sku"

        init_facts = [
            {"predicate": "carrier_at", "arguments": ["agv_1", zone_names[0]]},
            {"predicate": "carrier_empty", "arguments": ["agv_1"]},
        ]
        # Connect zones linearly
        for i in range(len(zone_names) - 1):
            init_facts.append({"predicate": "zone_connected", "arguments": [zone_names[i], zone_names[i+1]]})
            init_facts.append({"predicate": "zone_connected", "arguments": [zone_names[i+1], zone_names[i]]})

        # Distribute bays into zones
        for idx, b in enumerate(bay_names):
            z = zone_names[idx % len(zone_names)]
            init_facts.append({"predicate": "bay_in_zone", "arguments": [b, z]})
            if idx > 0:
                init_facts.append({"predicate": "bay_available", "arguments": [b]})

        for s in range(1, n_skus + 1):
            init_facts.append({"predicate": "sku_stored_in", "arguments": [f"sku_{s}", bay_names[0]]})

        goal_bay = bay_names[-1]
        goal_facts = [{"predicate": "sku_stored_in", "arguments": ["sku_1", goal_bay]}]
        prompt = f"Move sku_1 from {bay_names[0]} to {goal_bay} in {tier.value} logistics configuration."
        est_states = n_zones * ((n_bays + 1) ** n_skus)
        return MultiDomainBenchmarkInstance(
            instance_id=inst_id,
            domain_id="warehouse",
            tier=tier,
            prompt=prompt,
            entities=entities,
            initial_facts=init_facts,
            goal_conditions=goal_facts,
            estimated_state_space=est_states,
        )

    def _gen_scheduling(self, inst_id: str, tier: ComplexityTier) -> MultiDomainBenchmarkInstance:
        tier_configs = {
            ComplexityTier.TINY: (1, 2, 2),   # 1 machine, 2 slots, 2 jobs (~7 states)
            ComplexityTier.SMALL: (1, 2, 3),  # 1 machine, 2 slots, 3 jobs (~13 states)
            ComplexityTier.MEDIUM: (2, 2, 3), # 2 machines, 2 slots, 3 jobs (~73 states)
            ComplexityTier.LARGE: (2, 2, 4),  # 2 machines, 2 slots, 4 jobs (~250 states)
            ComplexityTier.STRESS: (3, 3, 5), # 3 machines, 3 slots, 5 jobs (>1000 states)
        }
        n_machines, n_slots, n_jobs = tier_configs.get(tier, (1, 2, 2))
        entities = {}
        for m in range(1, n_machines + 1):
            entities[f"machine_{m}"] = "resource"
        for s in range(1, n_slots + 1):
            entities[f"slot_{s}"] = "slot"
        for j in range(1, n_jobs + 1):
            entities[f"task_{j}"] = "job"

        init_facts = []
        for m in range(1, n_machines + 1):
            for s in range(1, n_slots + 1):
                init_facts.append({"predicate": "resource_available", "arguments": [f"machine_{m}", f"slot_{s}"]})

        for j in range(1, n_jobs + 1):
            init_facts.append({"predicate": "job_ready", "arguments": [f"task_{j}"]})

        if n_jobs >= 2:
            init_facts.append({"predicate": "precedes", "arguments": ["task_1", "task_2"]})

        goal_facts = [{"predicate": "job_completed", "arguments": [f"task_{n_jobs}"]}]
        prompt = f"Schedule tasks on available resources satisfying DAG precedence in {tier.value} configuration."
        est_states = (n_machines * n_slots + 1) ** (n_jobs - 1)
        return MultiDomainBenchmarkInstance(
            instance_id=inst_id,
            domain_id="scheduling",
            tier=tier,
            prompt=prompt,
            entities=entities,
            initial_facts=init_facts,
            goal_conditions=goal_facts,
            estimated_state_space=est_states,
        )

    def _gen_software(self, inst_id: str, tier: ComplexityTier) -> MultiDomainBenchmarkInstance:
        tier_configs = {
            ComplexityTier.TINY: (1, 1, 1),   # 1 commit, 1 artifact, 1 env (staging) (~9 states)
            ComplexityTier.SMALL: (1, 1, 2),  # 1 commit, 1 artifact, 2 envs (staging, prod) (~16 states)
            ComplexityTier.MEDIUM: (2, 2, 2), # 2 commits, 2 artifacts, 2 envs (~64 states)
            ComplexityTier.LARGE: (2, 2, 3),  # 2 commits, 2 artifacts, 3 envs (~340 states)
            ComplexityTier.STRESS: (3, 3, 3), # 3 commits, 3 artifacts, 3 envs (>1000 states)
        }
        n_commits, n_artifacts, n_envs = tier_configs.get(tier, (1, 1, 1))
        all_envs = ["dev", "staging", "prod"][:n_envs]
        entities = {}
        for c in range(1, n_commits + 1):
            entities[f"commit_{c}"] = "commit"
        for a in range(1, n_artifacts + 1):
            entities[f"pkg_{a}"] = "artifact"
        for e in all_envs:
            entities[e] = "environment"

        init_facts = []
        for c in range(1, n_commits + 1):
            init_facts.append({"predicate": "code_checked_out", "arguments": [f"commit_{c}"]})
        for e in all_envs:
            init_facts.append({"predicate": "environment_healthy", "arguments": [e]})

        dest_env = all_envs[-1]
        goal_facts = [{"predicate": "deployed_to", "arguments": ["pkg_1", dest_env]}]
        prompt = f"Build, test, scan, and deploy commit_1 to {dest_env} environment ({tier.value} pipeline)."
        est_states = (2 ** n_commits) * (n_envs + 1) ** n_artifacts
        return MultiDomainBenchmarkInstance(
            instance_id=inst_id,
            domain_id="software_workflow",
            tier=tier,
            prompt=prompt,
            entities=entities,
            initial_facts=init_facts,
            goal_conditions=goal_facts,
            estimated_state_space=est_states,
        )

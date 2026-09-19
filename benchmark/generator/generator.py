"""Procedural benchmark problem generator for reproducible experiments."""

from __future__ import annotations

import random
from typing import Dict, List, Optional
from core.contracts import BenchmarkInstanceSchema, FactSchema, FaultClass


class BenchmarkGenerator:
    """Procedurally generates benchmark instances with controlled difficulty and optional faults."""

    def __init__(self, seed: int = 42) -> None:
        self.seed = seed
        self.rng = random.Random(seed)

    def generate_suite(
        self,
        domain_name: str = "blocks_world",
        count: int = 10,
        inject_faults: bool = True,
    ) -> List[BenchmarkInstanceSchema]:
        """Generates a suite of benchmark problem instances."""
        instances: List[BenchmarkInstanceSchema] = []

        for i in range(count):
            inst_seed = self.seed + i * 13
            rng = random.Random(inst_seed)

            num_blocks = rng.choice([2, 3, 4])
            block_names = [f"b{j+1}" for j in range(num_blocks)]
            objects = {b: "block" for b in block_names}

            # Generate random legal initial configuration (all on table for simplicity)
            initial_facts = [FactSchema(predicate="handempty", arguments=())]
            for b in block_names:
                initial_facts.append(FactSchema(predicate="on_table", arguments=(b,)))
                initial_facts.append(FactSchema(predicate="clear", arguments=(b,)))

            # Goal configuration: stack a subset of blocks, e.g. b1 on b2
            goal_facts = [
                FactSchema(predicate="on", arguments=(block_names[0], block_names[1]))
            ]
            if num_blocks >= 3 and rng.random() > 0.5:
                goal_facts.append(
                    FactSchema(predicate="on", arguments=(block_names[1], block_names[2]))
                )

            # Optional injected fault
            injected_fault: Optional[FaultClass] = None
            if inject_faults and (i % 2 == 1):
                fault_options = [
                    FaultClass.PLANNING_ERROR,
                    FaultClass.FORMALIZATION_ERROR,
                    FaultClass.PERCEPTION_ERROR,
                ]
                injected_fault = rng.choice(fault_options)

            difficulty = "easy" if num_blocks == 2 else ("medium" if num_blocks == 3 else "hard")
            inst_id = f"BENCH-{domain_name[:3].upper()}-{i+1:03d}"
            prompt = f"Stack {block_names[0]} on {block_names[1]}."

            instance = BenchmarkInstanceSchema(
                instance_id=inst_id,
                domain=domain_name,
                name=f"{domain_name}_inst_{i+1}",
                difficulty=difficulty,
                objects=objects,
                initial_facts=initial_facts,
                goal_facts=goal_facts,
                natural_language_prompt=prompt,
                injected_fault_type=injected_fault,
                known_optimal_cost=float(len(goal_facts) * 2),
            )
            instances.append(instance)

        return instances

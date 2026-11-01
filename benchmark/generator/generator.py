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

            tier = i % 3
            if tier == 0:
                difficulty = "easy"
                num_blocks = 3
            elif tier == 1:
                difficulty = "medium"
                num_blocks = 4
            else:
                difficulty = "hard"
                num_blocks = rng.choice([5, 6])

            block_names = [f"b{j+1}" for j in range(num_blocks)]
            objects = {b: "block" for b in block_names}

            # Goal configuration: target stack of 2 to 3 blocks without cycles
            goal_candidates = list(block_names)
            rng.shuffle(goal_candidates)
            num_goals = 2 if (len(goal_candidates) >= 3 and difficulty in ("medium", "hard")) else 1
            goal_facts: List[FactSchema] = [
                FactSchema(predicate="on", arguments=(goal_candidates[0], goal_candidates[1]))
            ]
            if num_goals == 2:
                goal_facts.append(
                    FactSchema(predicate="on", arguments=(goal_candidates[1], goal_candidates[2]))
                )

            goal_block_set = set(goal_candidates[:(num_goals + 1)])
            available_protected = [b for b in block_names if b not in goal_block_set]
            protected = rng.choice(available_protected) if (difficulty in ("medium", "hard") and available_protected) else None

            # Optional hard constraint for medium/hard
            constraints: List[FactSchema] = []
            if protected:
                constraints.append(
                    FactSchema(predicate="holding", arguments=(protected,), is_negated=True)
                )

            # Generate valid initial state:
            # If protected exists, keep it isolated on table so problem is provably solvable
            active_blocks = [b for b in block_names if b != protected]
            initial_facts: List[FactSchema] = [FactSchema(predicate="handempty", arguments=())]
            if protected:
                initial_facts.append(FactSchema(predicate="on_table", arguments=(protected,)))
                initial_facts.append(FactSchema(predicate="clear", arguments=(protected,)))

            num_stacks = rng.randint(1, min(len(active_blocks), 3))
            stacks: List[List[str]] = [[] for _ in range(num_stacks)]
            shuffled = list(active_blocks)
            rng.shuffle(shuffled)
            for idx, b in enumerate(shuffled):
                stacks[idx % num_stacks].append(b)

            for stack in stacks:
                if not stack:
                    continue
                # Base is on table
                initial_facts.append(FactSchema(predicate="on_table", arguments=(stack[0],)))
                # Intermediate blocks
                for s_idx in range(len(stack) - 1):
                    initial_facts.append(
                        FactSchema(predicate="on", arguments=(stack[s_idx + 1], stack[s_idx]))
                    )
                # Top is clear
                initial_facts.append(FactSchema(predicate="clear", arguments=(stack[-1],)))

            # Optional injected fault
            injected_fault: Optional[FaultClass] = None
            if inject_faults and (i % 2 == 1):
                fault_options = [
                    FaultClass.PLANNING_ERROR,
                    FaultClass.FORMALIZATION_ERROR,
                    FaultClass.PERCEPTION_ERROR,
                    FaultClass.ENVIRONMENT_CHANGE,
                ]
                injected_fault = rng.choice(fault_options)

            inst_id = f"BENCH-{domain_name[:3].upper()}-{i+1:03d}"
            prompt = f"Stack {goal_candidates[0]} on {goal_candidates[1]}."
            if constraints:
                prompt += f" Do not touch or move {block_names[-1]}."

            instance = BenchmarkInstanceSchema(
                instance_id=inst_id,
                domain=domain_name,
                name=f"{domain_name}_inst_{i+1}",
                difficulty=difficulty,
                objects=objects,
                initial_facts=initial_facts,
                goal_facts=goal_facts,
                constraints=constraints,
                natural_language_prompt=prompt,
                injected_fault_type=injected_fault,
                known_optimal_cost=float(len(goal_facts) * 2),
            )
            instances.append(instance)

        return instances

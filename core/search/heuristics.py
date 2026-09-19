"""Domain-independent planning heuristics for Best-First and A* search."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Sequence, Set
from core.actions.instantiation import GroundAction
from core.world.predicates import Fact
from core.world.state import SymbolicState


class Heuristic(ABC):
    """Base class for goal-directed distance estimation."""

    @abstractmethod
    def compute(self, state: SymbolicState, goal_conditions: Sequence[Fact]) -> float:
        pass


class ZeroHeuristic(Heuristic):
    """Blind zero heuristic (reduces A* to Uniform-Cost Search / Dijkstra)."""

    def compute(self, state: SymbolicState, goal_conditions: Sequence[Fact]) -> float:
        return 0.0


class GoalCountHeuristic(Heuristic):
    """Counts how many goal atoms are currently unsatisfied in the state."""

    def compute(self, state: SymbolicState, goal_conditions: Sequence[Fact]) -> float:
        unmet = state.find_unmet_conditions(goal_conditions)
        return float(len(unmet))


class RelaxedPlanningGraphHeuristic(Heuristic):
    """Delete-Relaxation Heuristic (h_max or h_add) using relaxed planning graph layers."""

    def __init__(self, ground_actions: Sequence[GroundAction], mode: str = "h_max") -> None:
        self.ground_actions = tuple(ground_actions)
        self.mode = mode.lower()  # "h_max" (admissible) or "h_add"

    def compute(self, state: SymbolicState, goal_conditions: Sequence[Fact]) -> float:
        unmet = state.find_unmet_conditions(goal_conditions)
        if not unmet:
            return 0.0

        # Layer 0 facts
        known_facts: Set[Fact] = set(state.facts)
        fact_costs: Dict[Fact, int] = {f: 0 for f in state.facts}
        applicable_actions = set(self.ground_actions)

        layer = 0
        max_layers = 100

        while layer < max_layers:
            # Check if all goal conditions have costs assigned
            if all(g in fact_costs for g in unmet):
                if self.mode == "h_max":
                    return float(max(fact_costs[g] for g in unmet))
                else:  # h_add
                    return float(sum(fact_costs[g] for g in unmet))

            new_facts_in_layer: Set[Fact] = set()
            used_actions: Set[GroundAction] = set()

            for act in applicable_actions:
                # Preconditions must all exist in known facts
                if all(p in fact_costs for p in act.preconditions if not p.is_negated):
                    used_actions.add(act)
                    act_cost = 1 + (
                        max((fact_costs[p] for p in act.preconditions if not p.is_negated), default=0)
                    )
                    for add in act.add_effects:
                        if not add.is_negated:
                            new_facts_in_layer.add(add)
                            if add not in fact_costs or act_cost < fact_costs[add]:
                                fact_costs[add] = act_cost

            if not new_facts_in_layer.issubset(known_facts):
                known_facts.update(new_facts_in_layer)
                applicable_actions -= used_actions
                layer += 1
            else:
                # Fixpoint reached without satisfying all goals (dead end or unreachable)
                return 9999.0

        return 9999.0

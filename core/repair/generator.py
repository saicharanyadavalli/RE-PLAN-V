"""Repair constraint generation grounded in counterexample evidence."""

from __future__ import annotations

import uuid
from typing import Optional
from core.actions.domain import Domain
from core.actions.instantiation import GroundAction
from core.contracts import (
    CounterexampleSchema,
    FaultAttributionSchema,
    FaultClass,
    RepairType,
    ViolationType,
)
from core.repair.models import RepairConstraint
from core.world.predicates import Fact
from core.world.problem import SymbolicProblem
from core.world.state import SymbolicState


class RepairGenerator:
    """Derives explicit, structured repair constraints from counterexamples and attribution."""

    def generate(
        self,
        counterexample: CounterexampleSchema,
        attribution: FaultAttributionSchema,
        problem: SymbolicProblem,
        domain: Domain,
    ) -> RepairConstraint:
        repair_id = f"REP-{uuid.uuid4().hex[:8].upper()}"

        # Reconstruct GroundAction from counterexample
        offending_action = GroundAction(
            name=counterexample.offending_action.name,
            arguments=counterexample.offending_action.arguments,
            preconditions=[],
            add_effects=[],
            del_effects=[],
            cost=counterexample.offending_action.cost,
        )

        # Snapshot state facts
        state_facts = frozenset(
            Fact.from_schema(f) for f in counterexample.state_snapshot.facts
        )

        # 1. PLANNING_ERROR Repair
        if attribution.fault_class == FaultClass.PLANNING_ERROR:
            if counterexample.failure_category == ViolationType.HARD_CONSTRAINT_VIOLATED:
                return RepairConstraint(
                    repair_id=repair_id,
                    repair_type=RepairType.FORBID_GROUND_ACTION,
                    description=f"Permanently forbid action '{offending_action.to_string()}' violating hard safety constraint.",
                    source_counterexample_id=counterexample.counterexample_id,
                    forbidden_action=offending_action,
                )
            else:
                return RepairConstraint(
                    repair_id=repair_id,
                    repair_type=RepairType.FORBID_ACTION_IN_STATE,
                    description=(
                        f"Forbid executing action '{offending_action.to_string()}' from state configuration "
                        f"at step {counterexample.action_index} because precondition '{counterexample.violated_condition.to_string()}' failed."
                    ),
                    source_counterexample_id=counterexample.counterexample_id,
                    forbidden_action=offending_action,
                    forbidden_state_facts=state_facts,
                )

        # 2. FORMALIZATION_ERROR Repair
        elif attribution.fault_class == FaultClass.FORMALIZATION_ERROR:
            return RepairConstraint(
                repair_id=repair_id,
                repair_type=RepairType.FORBID_GROUND_ACTION,
                description=f"Enforce missing formal constraint: forbid action on protected entity '{counterexample.affected_entities}'.",
                source_counterexample_id=counterexample.counterexample_id,
                forbidden_action=offending_action,
            )

        # 3. PERCEPTION_ERROR Repair
        elif attribution.fault_class == FaultClass.PERCEPTION_ERROR:
            violated = Fact.from_schema(counterexample.violated_condition)
            # If perception falsely believed it was true, delete it from state
            del_corrections = [violated] if not counterexample.actual_truth else []
            add_corrections = [violated] if counterexample.actual_truth else []
            return RepairConstraint(
                repair_id=repair_id,
                repair_type=RepairType.STATE_BELIEF_CORRECTION,
                description=f"Correct state belief discrepancy for condition '{violated.to_string()}'.",
                source_counterexample_id=counterexample.counterexample_id,
                state_corrections_add=add_corrections,
                state_corrections_del=del_corrections,
            )

        # 4. ENVIRONMENT_CHANGE Repair
        elif attribution.fault_class == FaultClass.ENVIRONMENT_CHANGE:
            return RepairConstraint(
                repair_id=repair_id,
                repair_type=RepairType.REFRESH_OBSERVATION,
                description="Synchronize world model with updated environment observations before replanning.",
                source_counterexample_id=counterexample.counterexample_id,
            )

        # 5. Fallback / UNKNOWN_AMBIGUOUS
        return RepairConstraint(
            repair_id=repair_id,
            repair_type=RepairType.FORBID_ACTION_IN_STATE,
            description=f"Prune failing transition '{offending_action.to_string()}' in state.",
            source_counterexample_id=counterexample.counterexample_id,
            forbidden_action=offending_action,
            forbidden_state_facts=state_facts,
        )

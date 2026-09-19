"""Repair constraints and explicit repair models."""

from __future__ import annotations

from typing import FrozenSet, List, Optional, Sequence
from core.actions.instantiation import GroundAction
from core.contracts import GroundActionSchema, RepairConstraintSchema, RepairType
from core.world.predicates import Fact
from core.world.state import SymbolicState


class RepairConstraint:
    """An explicit, evidence-derived search restriction or state correction."""

    def __init__(
        self,
        repair_id: str,
        repair_type: RepairType,
        description: str,
        source_counterexample_id: str,
        forbidden_action: Optional[GroundAction] = None,
        forbidden_state_facts: Optional[FrozenSet[Fact]] = None,
        before_action: Optional[GroundAction] = None,
        after_action: Optional[GroundAction] = None,
        state_corrections_add: Optional[Sequence[Fact]] = None,
        state_corrections_del: Optional[Sequence[Fact]] = None,
    ) -> None:
        self.repair_id = repair_id
        self.repair_type = repair_type
        self.description = description
        self.source_counterexample_id = source_counterexample_id
        self.forbidden_action = forbidden_action
        self.forbidden_state_facts = forbidden_state_facts
        self.before_action = before_action
        self.after_action = after_action
        self.state_corrections_add = tuple(state_corrections_add or [])
        self.state_corrections_del = tuple(state_corrections_del or [])

    def prunes_transition(self, state: SymbolicState, action: GroundAction) -> bool:
        """Evaluates whether (state, action) is forbidden by this repair constraint during search."""
        if self.repair_type == RepairType.FORBID_GROUND_ACTION:
            if self.forbidden_action and action == self.forbidden_action:
                return True

        elif self.repair_type == RepairType.FORBID_ACTION_IN_STATE:
            if self.forbidden_action and action == self.forbidden_action:
                if self.forbidden_state_facts is not None:
                    # If state contains all facts that defined the failure state
                    if self.forbidden_state_facts.issubset(state.facts):
                        return True

        return False

    def to_schema(self) -> RepairConstraintSchema:
        return RepairConstraintSchema(
            repair_id=self.repair_id,
            repair_type=self.repair_type,
            description=self.description,
            source_counterexample_id=self.source_counterexample_id,
            forbidden_action=self.forbidden_action.to_schema() if self.forbidden_action else None,
            forbidden_state_facts=[f.to_schema() for f in sorted(self.forbidden_state_facts)] if self.forbidden_state_facts else None,
            before_action=self.before_action.to_schema() if self.before_action else None,
            after_action=self.after_action.to_schema() if self.after_action else None,
            state_corrections_add=[f.to_schema() for f in self.state_corrections_add] if self.state_corrections_add else None,
            state_corrections_del=[f.to_schema() for f in self.state_corrections_del] if self.state_corrections_del else None,
        )

    def __repr__(self) -> str:
        return f"Repair({self.repair_type.value}, desc='{self.description}')"

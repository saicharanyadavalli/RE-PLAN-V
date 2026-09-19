"""Authoritative Action Transition Semantics.

NON-NEGOTIABLE RULE 3:
Planner and verifier MUST use the exact same action definitions, preconditions,
effects, and transition semantics. This function is the single source of truth.
"""

from __future__ import annotations

from typing import Optional, Tuple
from core.actions.instantiation import GroundAction
from core.world.state import SymbolicState


def apply_transition(
    state: SymbolicState, action: GroundAction
) -> Tuple[SymbolicState, Optional[str]]:
    """Applies an action to a state under authoritative STRIPS semantics.

    Returns:
        (new_state, None) on success.
        (current_state, error_message) on failure.
    """
    is_applicable, unmet_pre = action.is_applicable(state)
    if not is_applicable:
        return (
            state,
            f"Precondition unmet for action '{action.to_string()}': condition '{unmet_pre}' does not hold in current state.",
        )

    # Apply deletes first, then adds (canonical STRIPS semantics)
    new_state = state.apply_effects(
        adds=action.add_effects,
        dels=action.del_effects,
        new_step_index=state.step_index + 1,
    )
    return new_state, None

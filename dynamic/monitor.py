"""World observation comparator and delta calculator."""

from __future__ import annotations

import uuid
from typing import List, Sequence, Set, Tuple
from core.contracts import FactSchema, WorldDeltaSchema
from core.world.predicates import Fact
from core.world.state import SymbolicState


class WorldDeltaMonitor:
    """Monitors environment changes and calculates formal WorldDelta."""

    def compute_delta(
        self,
        previous_state: SymbolicState,
        new_observation_facts: Sequence[FactSchema],
    ) -> WorldDeltaSchema:
        """Computes added and removed facts between previous belief state and new observation."""
        prev_facts_set = {
            (f.predicate.lower(), tuple(f.arguments)) for f in previous_state.facts
        }
        new_facts_set = {
            (f.predicate.lower(), tuple(f.arguments))
            for f in new_observation_facts
            if not f.is_negated
        }

        # Calculate added facts
        added_tuples = new_facts_set - prev_facts_set
        added_facts = [
            FactSchema(predicate=p, arguments=args, is_negated=False)
            for p, args in sorted(added_tuples)
        ]

        # Calculate removed facts
        removed_tuples = prev_facts_set - new_facts_set
        removed_facts = [
            FactSchema(predicate=p, arguments=args, is_negated=False)
            for p, args in sorted(removed_tuples)
        ]

        # Extract affected entities
        affected_entities_set: Set[str] = set()
        for f in added_facts:
            affected_entities_set.update(f.arguments)
        for f in removed_facts:
            affected_entities_set.update(f.arguments)

        delta_id = f"DELTA-{uuid.uuid4().hex[:8].upper()}"
        explanation = (
            f"{len(added_facts)} facts added, {len(removed_facts)} facts removed. "
            f"Entities affected: {sorted(list(affected_entities_set))}."
        )

        return WorldDeltaSchema(
            delta_id=delta_id,
            added_facts=added_facts,
            removed_facts=removed_facts,
            affected_entities=sorted(list(affected_entities_set)),
            is_plan_invalidating=False,
            explanation=explanation,
        )

"""Legal action generation across state and domain objects."""

from __future__ import annotations

import itertools
from typing import Dict, Iterable, List, Optional, Sequence
from core.actions.definition import ActionDefinition
from core.actions.instantiation import GroundAction
from core.world.state import SymbolicState
from core.world.types import ObjectRegistry


class LegalActionGenerator:
    """Generates valid parameter bindings and filters for applicable ground actions."""

    def __init__(self, actions: Sequence[ActionDefinition], registry: ObjectRegistry) -> None:
        self.actions = tuple(actions)
        self.registry = registry

    def generate_all_ground_actions(self) -> List[GroundAction]:
        """Generates all syntactically valid ground actions in the domain object universe."""
        all_ground: List[GroundAction] = []
        for act_def in self.actions:
            param_candidates: List[List[str]] = []
            for param in act_def.parameters:
                objs = self.registry.get_objects_of_type(param.type_name)
                param_candidates.append(objs)

            for combo in itertools.product(*param_candidates):
                binding = {param.name: obj for param, obj in zip(act_def.parameters, combo)}
                ground_action = act_def.instantiate(binding)
                all_ground.append(ground_action)
        return all_ground

    def get_applicable_actions(self, state: SymbolicState) -> List[GroundAction]:
        """Generates all legal ground actions whose preconditions hold in the current state."""
        applicable: List[GroundAction] = []
        for act_def in self.actions:
            param_candidates: List[List[str]] = []
            for param in act_def.parameters:
                objs = self.registry.get_objects_of_type(param.type_name)
                param_candidates.append(objs)

            for combo in itertools.product(*param_candidates):
                binding = {param.name: obj for param, obj in zip(act_def.parameters, combo)}
                ground_action = act_def.instantiate(binding)
                is_ok, _ = ground_action.is_applicable(state)
                if is_ok:
                    applicable.append(ground_action)
        return applicable

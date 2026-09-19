"""Forward-chaining inference engine for Horn clauses."""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Sequence, Set
from core.krr.rules import Rule
from core.krr.unification import unify_literals
from core.world.predicates import Fact
from core.world.state import SymbolicState


class ForwardChainingEngine:
    """Bounded, deterministic forward chaining deductive inference engine."""

    def __init__(self, rules: Sequence[Rule], max_iterations: int = 50) -> None:
        self.rules = tuple(rules)
        self.max_iterations = max_iterations

    def infer(self, initial_facts: Iterable[Fact]) -> Set[Fact]:
        """Computes the deductive closure of initial_facts under the registered Horn rules."""
        known_facts: Set[Fact] = {f.positive_version() for f in initial_facts if not f.is_negated}

        for _ in range(self.max_iterations):
            new_facts_this_round: Set[Fact] = set()

            for rule in self.rules:
                # Find all substitutions that satisfy the entire body
                substitutions = self._match_body(rule.body, known_facts, [{}])

                for subst in substitutions:
                    # Ground the head
                    ground_head_args = [
                        subst.get(arg, arg) for arg in rule.head.arguments
                    ]
                    # Only derive if head is fully ground (no ? variables remaining)
                    if not any(a.startswith("?") for a in ground_head_args):
                        derived_fact = Fact(
                            rule.head.predicate, ground_head_args, is_negated=False
                        )
                        if derived_fact not in known_facts:
                            new_facts_this_round.add(derived_fact)

            if not new_facts_this_round:
                # Fixpoint reached
                break

            known_facts.update(new_facts_this_round)

        return known_facts

    def infer_for_state(self, state: SymbolicState) -> SymbolicState:
        """Returns a new state enriched with all derived deductive facts."""
        closure = self.infer(state.facts)
        return SymbolicState(
            facts=closure, objects=state.objects, step_index=state.step_index
        )

    def _match_body(
        self,
        body: Sequence[Fact],
        known_facts: Set[Fact],
        current_substs: List[Dict[str, str]],
    ) -> List[Dict[str, str]]:
        """Recursively matches body goals against known facts."""
        if not body:
            return current_substs

        first_goal = body[0]
        remaining_goals = body[1:]
        valid_extensions: List[Dict[str, str]] = []

        for subst in current_substs:
            # Partially ground the first goal with current subst
            inst_args = [subst.get(a, a) for a in first_goal.arguments]

            for fact in known_facts:
                if fact.predicate.lower() == first_goal.predicate.lower() and fact.arity == len(inst_args):
                    new_subst = unify_literals(
                        first_goal.predicate,
                        inst_args,
                        fact.predicate,
                        fact.arguments,
                        subst,
                    )
                    if new_subst is not None:
                        valid_extensions.append(new_subst)

        return self._match_body(remaining_goals, known_facts, valid_extensions)

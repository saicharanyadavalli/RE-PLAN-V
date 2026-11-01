"""First-Order Clause Form (CNF) and Resolution Refutation Engine.

Implements:
1. CNFClause: Disjunction of positive and negative first-order literals.
2. rule_to_cnf: Converts Horn rules (Head :- Body) into CNF clauses.
3. resolve: Binary resolution between two first-order clauses via MGU unification.
4. resolution_refutation: Derives empty clause (contradiction) by refutation.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Set, Tuple
from core.krr.rules import Rule
from core.krr.unification import unify_literals
from core.world.predicates import Fact


class CNFClause:
    """A First-Order clause in Conjunctive Normal Form (disjunction of literals).
    
    Example:
        not(on(?x, ?y)) OR above(?x, ?y)
    """

    def __init__(self, literals: Sequence[Fact], name: str = "") -> None:
        # Deduplicate literals while preserving order
        seen = set()
        deduped = []
        for lit in literals:
            key = (lit.predicate.lower(), tuple(lit.arguments), lit.is_negated)
            if key not in seen:
                seen.add(key)
                deduped.append(lit)
        self.literals: Tuple[Fact, ...] = tuple(deduped)
        self.name = name

    @property
    def is_empty(self) -> bool:
        """Returns True if this is the empty clause (contradiction, Box)."""
        return len(self.literals) == 0

    @property
    def positive_literals(self) -> List[Fact]:
        return [l for l in self.literals if not l.is_negated]

    @property
    def negative_literals(self) -> List[Fact]:
        return [l for l in self.literals if l.is_negated]

    def substitute(self, subst: Dict[str, str]) -> CNFClause:
        """Applies variable substitution to all literals in the clause."""
        new_lits = []
        for lit in self.literals:
            inst_args = tuple(subst.get(a, a) for a in lit.arguments)
            new_lits.append(Fact(lit.predicate, inst_args, is_negated=lit.is_negated))
        return CNFClause(new_lits, name=self.name)

    def __repr__(self) -> str:
        if self.is_empty:
            return "[] (EMPTY_CLAUSE)"
        parts = []
        for l in self.literals:
            if l.is_negated:
                parts.append(f"~{l.predicate}({', '.join(l.arguments)})")
            else:
                parts.append(f"{l.predicate}({', '.join(l.arguments)})")
        return " | ".join(parts)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CNFClause):
            return False
        return set((l.predicate.lower(), tuple(l.arguments), l.is_negated) for l in self.literals) == \
               set((l.predicate.lower(), tuple(l.arguments), l.is_negated) for l in other.literals)

    def __hash__(self) -> int:
        return hash(frozenset((l.predicate.lower(), tuple(l.arguments), l.is_negated) for l in self.literals))


def rule_to_cnf(rule: Rule) -> CNFClause:
    """Converts a definite Horn rule Head :- Body_1, ..., Body_k into CNF:
    
    (not(Body_1) OR ... OR not(Body_k) OR Head)
    """
    clause_lits: List[Fact] = []
    # Negative body literals
    for body_fact in rule.body:
        clause_lits.append(Fact(body_fact.predicate, body_fact.arguments, is_negated=True))
    # Positive head literal
    clause_lits.append(Fact(rule.head.predicate, rule.head.arguments, is_negated=False))
    return CNFClause(clause_lits, name=rule.name)


def resolve(c1: CNFClause, c2: CNFClause) -> List[Tuple[CNFClause, str]]:
    """Performs first-order binary resolution between two clauses.
    
    Finds a complementary pair (p in c1, ~q in c2 or vice versa) where p and q unify via MGU.
    Returns list of (resolvent_clause, explanation).
    """
    resolvents: List[Tuple[CNFClause, str]] = []

    for l1 in c1.literals:
        for l2 in c2.literals:
            # Check if complementary: same predicate, same arity, opposite negation
            if l1.predicate.lower() == l2.predicate.lower() and len(l1.arguments) == len(l2.arguments) and (l1.is_negated != l2.is_negated):
                mgu = unify_literals(l1.predicate, l1.arguments, l2.predicate, l2.arguments)
                if mgu is not None:
                    # Apply substitution
                    c1_sub = c1.substitute(mgu)
                    c2_sub = c2.substitute(mgu)
                    l1_sub = Fact(l1.predicate, tuple(mgu.get(a, a) for a in l1.arguments), is_negated=l1.is_negated)
                    l2_sub = Fact(l2.predicate, tuple(mgu.get(a, a) for a in l2.arguments), is_negated=l2.is_negated)

                    # Form resolvent: (c1 \ {l1_sub}) UNION (c2 \ {l2_sub})
                    new_lits = [
                        l for l in c1_sub.literals
                        if not (l.predicate.lower() == l1_sub.predicate.lower() and tuple(l.arguments) == tuple(l1_sub.arguments) and l.is_negated == l1_sub.is_negated)
                    ]
                    for l in c2_sub.literals:
                        if not (l.predicate.lower() == l2_sub.predicate.lower() and tuple(l.arguments) == tuple(l2_sub.arguments) and l.is_negated == l2_sub.is_negated):
                            new_lits.append(l)

                    resolvent = CNFClause(new_lits)
                    exp = f"Resolved on {l1.predicate} with MGU {mgu} -> {resolvent}"
                    resolvents.append((resolvent, exp))

    return resolvents


def resolution_refutation(
    clauses: Sequence[CNFClause],
    goal_to_prove: Fact,
    max_steps: int = 50,
) -> Tuple[bool, List[str]]:
    """Attempts to prove `goal_to_prove` by resolution refutation.
    
    Adds negated goal ~goal to clauses and applies resolution until empty clause is derived.
    Returns:
        (is_proved: bool, proof_steps: List[str])
    """
    trace: List[str] = []
    # 1. Negate the goal
    negated_goal_clause = CNFClause(
        [Fact(goal_to_prove.predicate, goal_to_prove.arguments, is_negated=not goal_to_prove.is_negated)],
        name="negated_goal",
    )
    trace.append(f"Goal to prove: {goal_to_prove.to_string()}")
    trace.append(f"Add negated goal clause: {negated_goal_clause}")

    clause_set: Set[CNFClause] = set(clauses)
    clause_set.add(negated_goal_clause)

    for step in range(1, max_steps + 1):
        new_clauses: Set[CNFClause] = set()
        clause_list = list(clause_set)

        for i in range(len(clause_list)):
            for j in range(i + 1, len(clause_list)):
                c1 = clause_list[i]
                c2 = clause_list[j]
                step_resolvents = resolve(c1, c2)

                for res_clause, exp in step_resolvents:
                    if res_clause.is_empty:
                        trace.append(f"Step {step}: {c1} + {c2} -> [] CONTRADICTION (Refutation Success)")
                        return True, trace

                    if res_clause not in clause_set:
                        new_clauses.add(res_clause)
                        trace.append(f"Step {step}: {c1} + {c2} -> {res_clause}")

        if not new_clauses.issubset(clause_set):
            clause_set.update(new_clauses)
        else:
            # Fixpoint reached without deriving empty clause
            break

    trace.append("Fixpoint reached without contradiction: goal not refutation-provable.")
    return False, trace

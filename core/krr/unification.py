"""Robinson's first-order logic unification algorithm."""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple
from core.krr.terms import Constant, Term, Variable, parse_term


def unify_terms(
    t1: Term, t2: Term, theta: Optional[Dict[str, Term]] = None
) -> Optional[Dict[str, Term]]:
    """Unifies two terms under existing substitution theta. Returns updated theta or None."""
    if theta is None:
        theta = {}

    # Resolve variables through substitution chain
    t1 = _resolve(t1, theta)
    t2 = _resolve(t2, theta)

    if t1 == t2:
        return theta

    if t1.is_variable():
        return _unify_var(t1.name, t2, theta)

    if t2.is_variable():
        return _unify_var(t2.name, t1, theta)

    # Both are constants and distinct
    return None


def _resolve(term: Term, theta: Dict[str, Term]) -> Term:
    """Follows variable bindings until a ground term or unbound variable is found."""
    while term.is_variable() and term.name in theta:
        term = theta[term.name]
    return term


def _unify_var(var_name: str, x: Term, theta: Dict[str, Term]) -> Optional[Dict[str, Term]]:
    """Binds variable to term with occurs check."""
    if var_name in theta:
        return unify_terms(theta[var_name], x, theta)
    if x.is_variable() and x.name in theta:
        return unify_terms(Variable(var_name), theta[x.name], theta)
    if x.is_variable() and x.name == var_name:
        return theta
    # Occurs check
    if _occurs_in(var_name, x, theta):
        return None

    new_theta = dict(theta)
    new_theta[var_name] = x
    return new_theta


def _occurs_in(var_name: str, term: Term, theta: Dict[str, Term]) -> bool:
    resolved = _resolve(term, theta)
    return resolved.is_variable() and resolved.name == var_name


def unify_literals(
    pred1: str,
    args1: Sequence[str],
    pred2: str,
    args2: Sequence[str],
    theta: Optional[Dict[str, str]] = None,
) -> Optional[Dict[str, str]]:
    """Unifies two logical literals. Predicates must match and arity must match."""
    if pred1.lower() != pred2.lower():
        return None
    if len(args1) != len(args2):
        return None

    # Convert str args to Terms
    t_theta: Dict[str, Term] = (
        {k: parse_term(v) for k, v in theta.items()} if theta else {}
    )

    for a1_str, a2_str in zip(args1, args2):
        t1 = parse_term(a1_str)
        t2 = parse_term(a2_str)
        res = unify_terms(t1, t2, t_theta)
        if res is None:
            return None
        t_theta = res

    # Convert back to string substitution
    result: Dict[str, str] = {}
    for k, v in t_theta.items():
        res_v = _resolve(v, t_theta)
        result[k] = res_v.name
    return result

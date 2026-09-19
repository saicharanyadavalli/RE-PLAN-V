"""Unit tests for Stage 4: Knowledge Representation and Reasoning (KR&R)."""

import pytest
from core.krr.terms import Constant, Variable, parse_term
from core.krr.unification import unify_literals, unify_terms
from core.krr.rules import Rule
from core.krr.inference import ForwardChainingEngine
from core.world.predicates import Fact
from core.world.state import SymbolicState


def test_terms_and_parsing():
    c = Constant("table")
    v = Variable("?x")
    v2 = Variable("x")  # Auto prepends '?'

    assert c.is_constant()
    assert not c.is_variable()
    assert v.is_variable()
    assert not v.is_constant()
    assert v == v2
    assert str(c) == "table"
    assert str(v) == "?x"

    parsed_c = parse_term("block1")
    parsed_v = parse_term("?b")
    assert isinstance(parsed_c, Constant)
    assert isinstance(parsed_v, Variable)


def test_term_unification():
    # 1. Same constants
    res = unify_terms(Constant("a"), Constant("a"))
    assert res == {}

    # 2. Distinct constants
    res = unify_terms(Constant("a"), Constant("b"))
    assert res is None

    # 3. Variable and constant
    res = unify_terms(Variable("?x"), Constant("a"))
    assert res == {"?x": Constant("a")}

    # 4. Variable and variable
    res = unify_terms(Variable("?x"), Variable("?y"))
    assert "?x" in res or "?y" in res


def test_literal_unification():
    # Unify on(?x, table) with on(b1, table)
    res = unify_literals("on", ["?x", "table"], "on", ["b1", "table"])
    assert res is not None
    assert res["?x"] == "b1"

    # Predicate mismatch
    res = unify_literals("on", ["?x", "table"], "at", ["b1", "table"])
    assert res is None

    # Arity mismatch
    res = unify_literals("on", ["?x"], "on", ["b1", "table"])
    assert res is None

    # Multiple variables
    res = unify_literals("connected", ["?x", "?y"], "connected", ["loc1", "loc2"])
    assert res == {"?x": "loc1", "?y": "loc2"}


def test_forward_chaining_transitive_above():
    """Rules:
    above(?x, ?y) :- on(?x, ?y)
    above(?x, ?z) :- on(?x, ?y), above(?y, ?z)
    """
    rule1 = Rule(
        head=Fact("above", ["?x", "?y"]),
        body=[Fact("on", ["?x", "?y"])],
        name="direct_above",
    )
    rule2 = Rule(
        head=Fact("above", ["?x", "?z"]),
        body=[Fact("on", ["?x", "?y"]), Fact("above", ["?y", "?z"])],
        name="transitive_above",
    )

    engine = ForwardChainingEngine(rules=[rule1, rule2])

    # Initial tower: A on B, B on C, C on table
    init_facts = [
        Fact("on", ["A", "B"]),
        Fact("on", ["B", "C"]),
        Fact("on", ["C", "table"]),
    ]

    closure = engine.infer(init_facts)

    assert Fact("above", ["A", "B"]) in closure
    assert Fact("above", ["B", "C"]) in closure
    assert Fact("above", ["C", "table"]) in closure
    assert Fact("above", ["A", "C"]) in closure
    assert Fact("above", ["A", "table"]) in closure
    assert Fact("above", ["B", "table"]) in closure

    # Ensure facts that don't hold are NOT in closure
    assert Fact("above", ["C", "A"]) not in closure


def test_forward_chaining_cycle_termination():
    """Rule with symmetric cycle:
    connected(?y, ?x) :- connected(?x, ?y)
    """
    rule_sym = Rule(
        head=Fact("connected", ["?y", "?x"]),
        body=[Fact("connected", ["?x", "?y"])],
    )

    engine = ForwardChainingEngine(rules=[rule_sym], max_iterations=10)
    init_facts = [Fact("connected", ["loc1", "loc2"])]

    closure = engine.infer(init_facts)
    assert Fact("connected", ["loc1", "loc2"]) in closure
    assert Fact("connected", ["loc2", "loc1"]) in closure
    assert len(closure) == 2  # Fixpoint reached without infinite loop

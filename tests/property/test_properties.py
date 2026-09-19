"""Section 19.12: Property and Invariant Testing."""

import pytest
from core.actions.domain import create_blocks_world_domain
from core.actions.instantiation import GroundAction
from core.actions.transition import apply_transition
from core.contracts import (
    FactSchema,
    GroundActionSchema,
    PlanSchema,
    SymbolicStateSchema,
    ViolationType,
)
from core.counterexamples.generator import CounterexampleGenerator
from dynamic.monitor import WorldDeltaMonitor
from core.repair.generator import RepairGenerator
from core.replanning.loop import ReplanningEngine
from core.search.algorithms import AStarPlanner, BFSPlanner, BestFirstPlanner
from core.verification.verifier import PlanVerifier
from core.world.constraints import NegativeFactInvariant
from core.world.predicates import Fact
from core.world.problem import SymbolicProblem
from core.world.state import SymbolicState
from core.world.types import ObjectRegistry


def make_problem(domain, objects: dict[str, str], init_facts, goal_facts, invariants=None) -> SymbolicProblem:
    reg = ObjectRegistry(domain.type_hierarchy)
    for obj, t in objects.items():
        reg.register_object(obj, t)
    init_state = SymbolicState(facts=init_facts, objects=reg.get_all_objects())
    return SymbolicProblem(
        name="PropertyProblem",
        domain_name=domain.name,
        registry=reg,
        initial_state=init_state,
        goal_conditions=goal_facts,
        invariants=invariants or [],
    )


class TestSystemProperties:
    """Mathematical and logical invariant properties of the RE-PLAN-V architecture."""

    def test_property_inapplicable_action_never_silently_succeeds(self):
        """Property: Applying an action whose preconditions are unmet returns False and does not alter state."""
        domain = create_blocks_world_domain()
        s0 = SymbolicState([Fact("on_table", ["b1"]), Fact("clear", ["b1"])], objects={"b1": "block"})
        stack_op = domain.get_action("stack")
        ground_stack = GroundAction(
            name="stack",
            arguments=("b1", "b2"),
            preconditions=stack_op.preconditions,
            add_effects=stack_op.add_effects,
            del_effects=stack_op.del_effects,
        )

        s1, err = apply_transition(s0, ground_stack)
        assert err is not None
        assert s1 == s0
        assert "Precondition" in err

    def test_property_verified_plan_strictly_satisfies_all_conditions(self):
        """Property: A plan declared valid by PlanVerifier strictly satisfies every precondition, invariant, and goal."""
        domain = create_blocks_world_domain()
        init_facts = [
            Fact("on_table", ["b1"]),
            Fact("on_table", ["b2"]),
            Fact("clear", ["b1"]),
            Fact("clear", ["b2"]),
            Fact("handempty", []),
        ]
        goal = [Fact("on", ["b1", "b2"])]
        problem = make_problem(domain, {"b1": "block", "b2": "block"}, init_facts, goal)

        planner = AStarPlanner()
        plan = planner.search(problem, domain)
        assert plan.is_success is True

        verifier = PlanVerifier()
        v_res = verifier.verify(problem, domain, plan)
        assert v_res.is_valid is True
        assert v_res.failed_step_index is None
        assert v_res.violation_type == ViolationType.NONE
        assert len(v_res.trace) == len(plan.actions)
        assert all(step.is_valid for step in v_res.trace)

    def test_property_deterministic_replay_produces_identical_state_trace(self):
        """Property: Executing a deterministic plan twice from identical state produces identical state traces."""
        domain = create_blocks_world_domain()
        init_facts = [
            Fact("on_table", ["b1"]),
            Fact("on_table", ["b2"]),
            Fact("clear", ["b1"]),
            Fact("clear", ["b2"]),
            Fact("handempty", []),
        ]
        problem = make_problem(domain, {"b1": "block", "b2": "block"}, init_facts, [Fact("on", ["b1", "b2"])])

        plan = PlanSchema(
            actions=[
                GroundActionSchema(name="pick_up", arguments=("b1",)),
                GroundActionSchema(name="stack", arguments=("b1", "b2")),
            ]
        )

        verifier = PlanVerifier()
        v1 = verifier.verify(problem, domain, plan)
        v2 = verifier.verify(problem, domain, plan)

        assert v1.is_valid == v2.is_valid
        assert len(v1.trace) == len(v2.trace)
        for s1, s2 in zip(v1.trace, v2.trace):
            assert s1.pre_state_facts_count == s2.pre_state_facts_count
            assert s1.post_state_facts_count == s2.post_state_facts_count

    def test_property_counterexamples_correspond_to_actual_verifier_failures(self):
        """Property: Counterexample generation extracts exact witness matching the verifier failure."""
        domain = create_blocks_world_domain()
        init_facts = [Fact("on_table", ["b1"]), Fact("clear", ["b1"]), Fact("handempty", [])]
        problem = make_problem(domain, {"b1": "block", "b2": "block"}, init_facts, [Fact("holding", ["b1"])])

        # Step 0 invalid: stack without pickup
        plan = PlanSchema(actions=[GroundActionSchema(name="stack", arguments=("b1", "b2"))])
        verifier = PlanVerifier()
        v_res = verifier.verify(problem, domain, plan)
        assert v_res.is_valid is False

        cex_gen = CounterexampleGenerator()
        cex = cex_gen.generate(v_res, problem)
        assert cex is not None
        assert cex.action_index == v_res.failed_step_index
        assert cex.violated_condition == v_res.violated_condition

    def test_property_repair_never_reintroduces_same_violation(self):
        """Property: Repaired plan prunes the specific offending action from the failing state."""
        domain = create_blocks_world_domain()
        init_facts = [Fact("on_table", ["b1"]), Fact("clear", ["b1"]), Fact("handempty", [])]
        problem = make_problem(domain, {"b1": "block", "b2": "block"}, init_facts, [Fact("holding", ["b1"])])

        engine = ReplanningEngine()
        broken_candidate = PlanSchema(actions=[GroundActionSchema(name="stack", arguments=("b1", "b2"))])
        res = engine.run_repair_loop(problem, domain, initial_candidate=broken_candidate)

        assert res.success is True
        assert res.repaired_plan is not None
        # The repaired plan must not have stack(b1, b2) as step 0
        assert res.repaired_plan.actions[0].name == "pick_up"

    def test_property_serialization_deserialization_is_lossless(self):
        """Property: Pydantic contracts roundtrip to JSON and back without semantic loss."""
        fact = FactSchema(predicate="on", arguments=("b1", "b2"), is_negated=False)
        json_str = fact.model_dump_json()
        fact_restored = FactSchema.model_validate_json(json_str)
        assert fact == fact_restored

        state_schema = SymbolicStateSchema(
            facts=[fact],
            objects={"b1": "block", "b2": "block"},
            step_index=3,
        )
        json_state = state_schema.model_dump_json()
        state_restored = SymbolicStateSchema.model_validate_json(json_state)
        assert state_schema == state_restored

    def test_property_search_algorithms_never_return_invalid_plan(self):
        """Property: Any successful plan produced by BFS, Best-First, or A* must be valid."""
        domain = create_blocks_world_domain()
        init_facts = [
            Fact("on_table", ["b1"]),
            Fact("on_table", ["b2"]),
            Fact("clear", ["b1"]),
            Fact("clear", ["b2"]),
            Fact("handempty", []),
        ]
        problem = make_problem(domain, {"b1": "block", "b2": "block"}, init_facts, [Fact("on", ["b1", "b2"])])

        verifier = PlanVerifier()
        for planner in [AStarPlanner(), BFSPlanner(), BestFirstPlanner()]:
            plan = planner.search(problem, domain)
            assert plan.is_success is True
            v_res = verifier.verify(problem, domain, plan)
            assert v_res.is_valid is True, f"{planner.name} returned an invalid plan!"

    def test_property_failed_verification_produces_structured_failure(self):
        """Property: PlanVerifier always produces structured failure metadata rather than raising uncaught exceptions."""
        domain = create_blocks_world_domain()
        problem = make_problem(domain, {"b1": "block"}, [], [Fact("holding", ["b1"])])
        invalid_plan = PlanSchema(actions=[GroundActionSchema(name="nonexistent_action", arguments=("b1",))])

        verifier = PlanVerifier()
        v_res = verifier.verify(problem, domain, invalid_plan)
        assert v_res.is_valid is False
        assert v_res.failed_step_index == 0
        assert v_res.explanation != ""

"""Section 19.10: Boundary and Edge-Case Testing."""

import pytest
from pydantic import ValidationError
from PIL import Image

from core.actions.domain import create_blocks_world_domain
from core.contracts import (
    FactSchema,
    GroundActionSchema,
    PlanSchema,
    TaskProposalSchema,
)
from dynamic.monitor import WorldDeltaMonitor
from dynamic.replanner import DynamicReplanner
from core.repair.generator import RepairGenerator
from core.replanning.loop import ReplanningEngine
from core.search.algorithms import AStarPlanner
from core.verification.verifier import PlanVerifier
from core.world.predicates import Fact
from core.world.problem import SymbolicProblem
from core.world.state import SymbolicState
from core.world.types import ObjectRegistry
from interpretation.llm.mock import MockLLMProvider
from interpretation.validator.validator import ConsistencyValidator
from interpretation.vision.detector import DeterministicSceneDetector


def make_problem(domain, objects: dict[str, str], init_facts, goal_facts) -> SymbolicProblem:
    reg = ObjectRegistry(domain.type_hierarchy)
    for obj, t in objects.items():
        reg.register_object(obj, t)
    init_state = SymbolicState(facts=init_facts, objects=reg.get_all_objects())
    return SymbolicProblem(
        name="EdgeCaseProblem",
        domain_name=domain.name,
        registry=reg,
        initial_state=init_state,
        goal_conditions=goal_facts,
    )


class TestEdgeCases:
    """Rigorous boundary and robustness checks."""

    def test_empty_state(self):
        """Empty state handling."""
        domain = create_blocks_world_domain()
        problem = make_problem(domain, {"b1": "block"}, [], [Fact("holding", ["b1"])])
        planner = AStarPlanner()
        plan = planner.search(problem, domain)
        # Cannot solve with empty state
        assert plan.is_success is False

    def test_empty_goal(self):
        """Empty goal: initially satisfied trivial problem."""
        domain = create_blocks_world_domain()
        init_facts = [Fact("on_table", ["b1"]), Fact("clear", ["b1"]), Fact("handempty", [])]
        problem = make_problem(domain, {"b1": "block"}, init_facts, [])
        planner = AStarPlanner()
        plan = planner.search(problem, domain)
        assert plan.is_success is True
        assert len(plan.actions) == 0

        verifier = PlanVerifier()
        v_res = verifier.verify(problem, domain, plan)
        assert v_res.is_valid is True

    def test_empty_plan(self):
        """Verifying an empty plan when goal is not satisfied."""
        domain = create_blocks_world_domain()
        init_facts = [Fact("on_table", ["b1"]), Fact("clear", ["b1"]), Fact("handempty", [])]
        problem = make_problem(domain, {"b1": "block"}, init_facts, [Fact("holding", ["b1"])])
        empty_plan = PlanSchema(actions=[])

        verifier = PlanVerifier()
        v_res = verifier.verify(problem, domain, empty_plan)
        assert v_res.is_valid is False

    def test_single_action_plan(self):
        """Single-action valid plan."""
        domain = create_blocks_world_domain()
        init_facts = [Fact("on_table", ["b1"]), Fact("clear", ["b1"]), Fact("handempty", [])]
        problem = make_problem(domain, {"b1": "block"}, init_facts, [Fact("holding", ["b1"])])
        plan = PlanSchema(actions=[GroundActionSchema(name="pick_up", arguments=("b1",))])

        verifier = PlanVerifier()
        v_res = verifier.verify(problem, domain, plan)
        assert v_res.is_valid is True

    def test_very_long_plan(self):
        """Verifying a long plan trace (>10 actions) executes deterministically."""
        domain = create_blocks_world_domain()
        init_facts = [
            Fact("on_table", ["b1"]),
            Fact("clear", ["b1"]),
            Fact("handempty", []),
        ]
        problem = make_problem(domain, {"b1": "block"}, init_facts, [Fact("on_table", ["b1"])])

        # Pick up and put down b1 repeatedly 6 times (12 actions total)
        actions = []
        for _ in range(6):
            actions.append(GroundActionSchema(name="pick_up", arguments=("b1",)))
            actions.append(GroundActionSchema(name="put_down", arguments=("b1",)))

        long_plan = PlanSchema(actions=actions)
        verifier = PlanVerifier()
        v_res = verifier.verify(problem, domain, long_plan)
        assert v_res.is_valid is True
        assert len(v_res.trace) == 12

    def test_zero_applicable_actions_deadlock(self):
        """Zero legal actions available in a deadlock state."""
        domain = create_blocks_world_domain()
        # State with no blocks on table and hand not empty but holding an unregistered entity
        problem = make_problem(domain, {}, [], [Fact("handempty", [])])
        planner = AStarPlanner()
        plan = planner.search(problem, domain)
        assert plan.is_success is False

    def test_duplicate_facts_in_state(self):
        """State handles duplicate facts cleanly via set semantics."""
        f1 = Fact("on_table", ["b1"])
        f2 = Fact("on_table", ["b1"])
        state = SymbolicState([f1, f2], objects={"b1": "block"})
        assert len(state.facts) == 1

    def test_contradictory_facts_rejected_by_validator(self):
        """ConsistencyValidator rejects direct contradictions: fact and not(fact)."""
        domain = create_blocks_world_domain()
        validator = ConsistencyValidator()
        proposal = TaskProposalSchema(
            task_id="contradiction",
            raw_prompt="b1 on table and not on table",
            entities={"b1": "block"},
            initial_facts=[
                FactSchema(predicate="on_table", arguments=("b1",), is_negated=False),
                FactSchema(predicate="on_table", arguments=("b1",), is_negated=True),
            ],
            goal_facts=[FactSchema(predicate="clear", arguments=("b1",))],
        )
        val_res = validator.validate(proposal, domain)
        assert val_res.is_valid is False
        assert any("Contradiction" in err for err in val_res.errors)

    def test_mutex_contradiction_rejected_by_validator(self):
        """Mutex violation: holding(b1) and on_table(b1) simultaneously."""
        domain = create_blocks_world_domain()
        validator = ConsistencyValidator()
        proposal = TaskProposalSchema(
            task_id="mutex_violation",
            raw_prompt="b1 is held and on table",
            entities={"b1": "block"},
            initial_facts=[
                FactSchema(predicate="holding", arguments=("b1",)),
                FactSchema(predicate="on_table", arguments=("b1",)),
            ],
            goal_facts=[FactSchema(predicate="clear", arguments=("b1",))],
        )
        val_res = validator.validate(proposal, domain)
        assert val_res.is_valid is False
        assert any("Mutex violation" in err for err in val_res.errors)

    def test_invalid_predicate_name_rejected_by_validator(self):
        """Unsupported predicate name is caught."""
        domain = create_blocks_world_domain()
        validator = ConsistencyValidator()
        proposal = TaskProposalSchema(
            task_id="unsupported_pred",
            raw_prompt="b1 is levitating",
            entities={"b1": "block"},
            initial_facts=[FactSchema(predicate="levitating", arguments=("b1",))],
            goal_facts=[],
        )
        val_res = validator.validate(proposal, domain)
        assert val_res.is_valid is False
        assert any("Unsupported predicate" in err for err in val_res.errors)

    def test_arity_mismatch_rejected_by_validator(self):
        """Arity mismatch: on_table requires 1 arg, given 2."""
        domain = create_blocks_world_domain()
        validator = ConsistencyValidator()
        proposal = TaskProposalSchema(
            task_id="arity_mismatch",
            raw_prompt="on_table(b1, b2)",
            entities={"b1": "block", "b2": "block"},
            initial_facts=[FactSchema(predicate="on_table", arguments=("b1", "b2"))],
            goal_facts=[],
        )
        val_res = validator.validate(proposal, domain)
        assert val_res.is_valid is False
        assert any("Arity mismatch" in err for err in val_res.errors)

    def test_unknown_entity_rejected_by_validator(self):
        """Proposal refers to an undeclared entity."""
        domain = create_blocks_world_domain()
        validator = ConsistencyValidator()
        proposal = TaskProposalSchema(
            task_id="undeclared_entity",
            raw_prompt="move mystery_box",
            entities={"b1": "block"},
            initial_facts=[FactSchema(predicate="on_table", arguments=("mystery_box",))],
            goal_facts=[],
        )
        val_res = validator.validate(proposal, domain)
        assert val_res.is_valid is False
        assert any("Unknown entity" in err for err in val_res.errors)

    def test_pydantic_schema_validation_immutability(self):
        """FactSchema is frozen and immutable."""
        f = FactSchema(predicate="on", arguments=("b1", "b2"))
        with pytest.raises(ValidationError):
            f.predicate = "something_else"  # type: ignore

    def test_empty_image_perception(self):
        """A plain blank white image with no blocks."""
        img = Image.new("RGB", (400, 400), color=(255, 255, 255))
        detector = DeterministicSceneDetector()
        detected = detector.detect(img)
        # No blocks detected on pure white canvas
        assert len(detected.detected_objects) == 0

    def test_irrelevant_vs_critical_environment_change(self):
        """Differentiates environment changes that break the plan vs those that do not."""
        domain = create_blocks_world_domain()
        init_facts = [
            Fact("on_table", ["b1"]),
            Fact("clear", ["b1"]),
            Fact("on_table", ["b2"]),
            Fact("clear", ["b2"]),
            Fact("handempty", []),
            Fact("on_table", ["b3"]),
            Fact("clear", ["b3"]),
        ]
        # Plan only interacts with b1 and b2
        problem = make_problem(domain, {"b1": "block", "b2": "block", "b3": "block"}, init_facts, [Fact("on", ["b1", "b2"])])
        planner = AStarPlanner()
        plan = planner.search(problem, domain)

        replanner = DynamicReplanner()

        # 1. Irrelevant change: b3 was removed
        obs_irrelevant = [
            FactSchema(predicate="on_table", arguments=("b1",)),
            FactSchema(predicate="clear", arguments=("b1",)),
            FactSchema(predicate="on_table", arguments=("b2",)),
            FactSchema(predicate="clear", arguments=("b2",)),
            FactSchema(predicate="handempty", arguments=()),
        ]
        replan_triggered, active_plan, delta = replanner.process_observation(
            current_state=problem.initial_state,
            remaining_plan=plan,
            problem=problem,
            domain=domain,
            new_observation_facts=obs_irrelevant,
        )
        assert replan_triggered is False

        # 2. Critical change: b1 was removed
        obs_critical = [
            FactSchema(predicate="on_table", arguments=("b2",)),
            FactSchema(predicate="clear", arguments=("b2",)),
            FactSchema(predicate="handempty", arguments=()),
        ]
        replan_triggered, active_plan, delta = replanner.process_observation(
            current_state=problem.initial_state,
            remaining_plan=plan,
            problem=problem,
            domain=domain,
            new_observation_facts=obs_critical,
        )
        assert replan_triggered is True

    def test_maximum_iteration_limit_enforcement(self):
        """ReplanningEngine strictly respects max_repair_iterations."""
        domain = create_blocks_world_domain()
        init_facts = [Fact("on_table", ["b1"]), Fact("clear", ["b1"]), Fact("handempty", [])]
        problem = make_problem(domain, {"b1": "block"}, init_facts, [Fact("holding", ["b1"])])

        engine = ReplanningEngine(max_repair_iterations=2)
        # Initial candidate fails
        candidate = PlanSchema(actions=[GroundActionSchema(name="stack", arguments=("b1", "b1"))])
        res = engine.run_repair_loop(problem, domain, initial_candidate=candidate)

        assert res.iterations <= 2

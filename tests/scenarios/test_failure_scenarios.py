"""Section 19.5: Invalid and Failure Scenarios F1 through F12."""

import pytest
from core.actions.domain import create_blocks_world_domain, create_gridworld_domain
from core.attribution.classifier import FaultAttributionEngine
from core.contracts import (
    FactSchema,
    FaultClass,
    GroundActionSchema,
    PlanSchema,
    TaskProposalSchema,
    ViolationType,
)
from core.counterexamples.generator import CounterexampleGenerator
from dynamic.monitor import WorldDeltaMonitor
from dynamic.replanner import DynamicReplanner
from core.repair.generator import RepairGenerator
from core.replanning.loop import ReplanningEngine
from core.search.algorithms import AStarPlanner
from core.verification.verifier import PlanVerifier
from core.world.constraints import NegativeFactInvariant, ProhibitedEntityActionConstraint
from core.world.predicates import Fact
from core.world.problem import SymbolicProblem
from core.world.state import SymbolicState
from core.world.types import ObjectRegistry
from interpretation.validator.validator import ConsistencyValidator


def make_problem(
    name: str,
    domain,
    objects: dict[str, str],
    init_facts,
    goal_facts,
    invariants=None,
    hard_constraints=None,
) -> SymbolicProblem:
    reg = ObjectRegistry(domain.type_hierarchy)
    for obj, t in objects.items():
        reg.register_object(obj, t)
    init_state = SymbolicState(facts=init_facts, objects=reg.get_all_objects())
    return SymbolicProblem(
        name=name,
        domain_name=domain.name,
        registry=reg,
        initial_state=init_state,
        goal_conditions=goal_facts,
        invariants=invariants or [],
        hard_constraints=hard_constraints or [],
    )


class TestFailureScenarios:
    """Verifies that all failure modes produce structured, diagnostic responses."""

    def test_scenario_f1_invalid_action_precondition(self):
        """F1: Invalid action precondition."""
        domain = create_blocks_world_domain()
        init_facts = [
            Fact("on_table", ["b1"]),
            Fact("clear", ["b1"]),
            Fact("handempty", []),
        ]
        problem = make_problem("F1_Precond", domain, {"b1": "block", "b2": "block"}, init_facts, [Fact("holding", ["b1"])])

        # Attempting stack without holding b1
        invalid_plan = PlanSchema(
            actions=[GroundActionSchema(name="stack", arguments=("b1", "b2"))]
        )

        verifier = PlanVerifier()
        v_res = verifier.verify(problem, domain, invalid_plan)

        assert v_res.is_valid is False
        assert v_res.failed_step_index == 0
        assert v_res.violation_type == ViolationType.PRECONDITION_UNMET
        assert v_res.violated_condition is not None
        assert v_res.violated_condition.predicate == "holding"

    def test_scenario_f2_invalid_state_transition(self):
        """F2: Invalid state transition (e.g. attempting action on non-clear block)."""
        domain = create_blocks_world_domain()
        init_facts = [
            Fact("on", ["b1", "b2"]),
            Fact("clear", ["b1"]),
            Fact("on_table", ["b2"]),
            Fact("handempty", []),
        ]
        problem = make_problem("F2_Transition", domain, {"b1": "block", "b2": "block"}, init_facts, [Fact("holding", ["b2"])])

        # Attempting to pick up b2 while b1 is on top of it (clear(b2) is false)
        invalid_plan = PlanSchema(
            actions=[GroundActionSchema(name="pick_up", arguments=("b2",))]
        )

        verifier = PlanVerifier()
        v_res = verifier.verify(problem, domain, invalid_plan)

        assert v_res.is_valid is False
        assert v_res.failed_step_index == 0
        assert v_res.violation_type == ViolationType.PRECONDITION_UNMET
        assert v_res.violated_condition.predicate == "clear"

    def test_scenario_f3_violated_invariant(self):
        """F3: Violated safety invariant."""
        domain = create_blocks_world_domain()
        # Invariant: Never hold fragile object 'glass'
        inv = NegativeFactInvariant(
            forbidden_fact=Fact("holding", ["glass"]),
            description="Safety constraint: glass must not be held",
        )
        init_facts = [
            Fact("on_table", ["glass"]),
            Fact("clear", ["glass"]),
            Fact("handempty", []),
        ]
        problem = make_problem(
            "F3_Invariant",
            domain,
            {"glass": "block"},
            init_facts,
            [Fact("on_table", ["glass"])],
            invariants=[inv],
        )

        # Plan picks up glass
        violating_plan = PlanSchema(
            actions=[GroundActionSchema(name="pick_up", arguments=("glass",))]
        )

        verifier = PlanVerifier()
        v_res = verifier.verify(problem, domain, violating_plan)

        assert v_res.is_valid is False
        assert v_res.violation_type == ViolationType.INVARIANT_VIOLATED
        assert "holding(glass)" in v_res.explanation

    def test_scenario_f4_violated_hard_constraint(self):
        """F4: Violated hard resource/boundary constraint."""
        domain = create_blocks_world_domain()
        # Constraint: action pick_up on glass is forbidden
        constraint = ProhibitedEntityActionConstraint(
            protected_entity="glass",
            prohibited_actions=["pick_up"],
            description="Hazardous to pick up glass",
        )
        init_facts = [
            Fact("on_table", ["glass"]),
            Fact("clear", ["glass"]),
            Fact("handempty", []),
        ]
        problem = make_problem(
            "F4_Constraint",
            domain,
            {"glass": "block"},
            init_facts,
            [Fact("holding", ["glass"])],
            hard_constraints=[constraint],
        )

        violating_plan = PlanSchema(
            actions=[GroundActionSchema(name="pick_up", arguments=("glass",))]
        )

        verifier = PlanVerifier()
        v_res = verifier.verify(problem, domain, violating_plan)
        assert v_res.is_valid is False
        assert v_res.violation_type == ViolationType.HARD_CONSTRAINT_VIOLATED

    def test_scenario_f5_incorrect_goal_state(self):
        """F5: Plan executes successfully but ends in unmet goal state."""
        domain = create_blocks_world_domain()
        init_facts = [
            Fact("on_table", ["b1"]),
            Fact("clear", ["b1"]),
            Fact("handempty", []),
        ]
        # Goal requires b1 stacked on b2, but plan only picks up b1
        problem = make_problem(
            "F5_UnmetGoal",
            domain,
            {"b1": "block", "b2": "block"},
            init_facts,
            [Fact("on", ["b1", "b2"])],
        )

        plan = PlanSchema(
            actions=[GroundActionSchema(name="pick_up", arguments=("b1",))]
        )

        verifier = PlanVerifier()
        v_res = verifier.verify(problem, domain, plan)

        assert v_res.is_valid is False
        assert v_res.violation_type == ViolationType.GOAL_UNMET
        assert "goal condition" in v_res.explanation.lower()

    def test_scenario_f6_incorrect_formalization(self):
        """F6: Incorrect formalization (neural hallucination of unknown entity or mutex contradiction)."""
        domain = create_blocks_world_domain()
        validator = ConsistencyValidator()

        # Proposal references unknown entity 'dragon'
        bad_proposal = TaskProposalSchema(
            task_id="f6_unknown",
            raw_prompt="Put the dragon on the table",
            entities={"b1": "block"},
            initial_facts=[FactSchema(predicate="on_table", arguments=("dragon",))],
            goal_facts=[FactSchema(predicate="on_table", arguments=("b1",))],
        )

        val_res = validator.validate(bad_proposal, domain)
        assert val_res.is_valid is False
        assert any("Unknown entity" in err for err in val_res.errors)

    def test_scenario_f7_incorrect_perception(self):
        """F7: Incorrect perception (visual scene discrepancy)."""
        attribution_engine = FaultAttributionEngine()
        domain = create_blocks_world_domain()
        init_facts = [Fact("on_table", ["b1"]), Fact("clear", ["b1"]), Fact("handempty", [])]
        problem = make_problem("F7_Percept", domain, {"b1": "block"}, init_facts, [Fact("holding", ["b1"])])

        invalid_plan = PlanSchema(actions=[GroundActionSchema(name="pick_up", arguments=("b1",))])
        verifier = PlanVerifier()

        # Simulate perception failure: b1 was believed to be clear in perception, but camera missed that it wasn't
        cex_gen = CounterexampleGenerator()
        v_res = verifier.verify(problem, domain, invalid_plan)
        v_res_fail = v_res.model_copy(update={
            "is_valid": False,
            "failed_step_index": 0,
            "violation_type": ViolationType.PRECONDITION_UNMET,
            "violated_condition": FactSchema(predicate="clear", arguments=("b1",)),
        })
        cex = cex_gen.generate(v_res_fail, problem)

        obs_facts = [FactSchema(predicate="clear", arguments=("b1",))]
        gt_facts = []  # Actually not clear in ground truth

        attr = attribution_engine.attribute(
            counterexample=cex,
            problem=problem,
            candidate_plan=invalid_plan,
            observed_facts=obs_facts,
            ground_truth_facts=gt_facts,
        )
        assert attr.fault_class == FaultClass.PERCEPTION_ERROR

    def test_scenario_f8_environment_changes_after_planning(self):
        """F8: Environment changes after planning."""
        domain = create_blocks_world_domain()
        init_facts = [
            Fact("on_table", ["b1"]),
            Fact("clear", ["b1"]),
            Fact("handempty", []),
        ]
        problem = make_problem("F8_EnvChange", domain, {"b1": "block"}, init_facts, [Fact("holding", ["b1"])])
        planner = AStarPlanner()
        plan = planner.search(problem, domain)

        # Before dispatch, someone steals b1
        replanner = DynamicReplanner()
        replan_triggered, active_plan, delta = replanner.process_observation(
            current_state=problem.initial_state,
            remaining_plan=plan,
            problem=problem,
            domain=domain,
            new_observation_facts=[FactSchema(predicate="handempty", arguments=())],
        )
        assert replan_triggered is True
        assert delta.is_plan_invalidating is True

    def test_scenario_f9_plan_invalid_midway_through_execution(self):
        """F9: Plan becomes invalid midway through execution trace."""
        domain = create_blocks_world_domain()
        init_facts = [
            Fact("on_table", ["b1"]),
            Fact("on_table", ["b2"]),
            Fact("clear", ["b1"]),
            Fact("clear", ["b2"]),
            Fact("handempty", []),
        ]
        problem = make_problem("F9_Midway", domain, {"b1": "block", "b2": "block"}, init_facts, [Fact("on", ["b1", "b2"])])

        # Step 0: pick_up(b1) -> Valid
        # Step 1: put_down(b2) -> Invalid, hand has b1, not b2
        invalid_midway_plan = PlanSchema(
            actions=[
                GroundActionSchema(name="pick_up", arguments=("b1",)),
                GroundActionSchema(name="put_down", arguments=("b2",)),
            ]
        )

        verifier = PlanVerifier()
        v_res = verifier.verify(problem, domain, invalid_midway_plan)

        assert v_res.is_valid is False
        assert v_res.failed_step_index == 1
        assert v_res.violation_type == ViolationType.PRECONDITION_UNMET
        assert v_res.violated_condition.predicate == "holding"

    def test_scenario_f10_repeated_repair_loop_detection(self):
        """F10: Repeated repair cycles are detected and terminated."""
        domain = create_blocks_world_domain()
        init_facts = [Fact("on_table", ["b1"]), Fact("clear", ["b1"]), Fact("handempty", [])]
        problem = make_problem("F10_Loop", domain, {"b1": "block"}, init_facts, [Fact("holding", ["b1"])])

        engine = ReplanningEngine(max_repair_iterations=5)
        # Force a cycle of identical counterexamples
        candidate = PlanSchema(actions=[GroundActionSchema(name="stack", arguments=("b1", "b1"))])
        res = engine.run_repair_loop(
            problem=problem,
            domain=domain,
            initial_candidate=candidate,
        )
        assert res.iterations <= 5

    def test_scenario_f11_no_valid_repair_exists(self):
        """F11: No valid repair exists (impossible goal with constraint)."""
        domain = create_blocks_world_domain()
        inv = NegativeFactInvariant(
            forbidden_fact=Fact("holding", ["b1"]),
            description="Forbidden to hold b1",
        )
        init_facts = [Fact("on_table", ["b1"]), Fact("clear", ["b1"]), Fact("handempty", [])]
        problem = make_problem("F11_Impossible", domain, {"b1": "block"}, init_facts, [Fact("holding", ["b1"])], invariants=[inv])

        engine = ReplanningEngine(max_repair_iterations=3)
        candidate = PlanSchema(actions=[GroundActionSchema(name="pick_up", arguments=("b1",))])
        res = engine.run_repair_loop(
            problem=problem,
            domain=domain,
            initial_candidate=candidate,
        )
        assert res.success is False
        assert res.status in ["NO_VERIFIED_PLAN", "LOOP_DETECTED", "MAX_ITERATIONS_REACHED"]

    def test_scenario_f12_no_valid_plan_exists_search_exhaustion(self):
        """F12: Search space exhausted when goal is unreachable."""
        domain = create_blocks_world_domain()
        # b2 doesn't exist in state
        init_facts = [Fact("on_table", ["b1"]), Fact("clear", ["b1"]), Fact("handempty", [])]
        problem = make_problem("F12_Unsolvable", domain, {"b1": "block"}, init_facts, [Fact("on", ["b1", "unreachable_b2"])])

        planner = AStarPlanner()
        plan = planner.search(problem, domain)
        assert plan.is_success is False
        assert len(plan.actions) == 0

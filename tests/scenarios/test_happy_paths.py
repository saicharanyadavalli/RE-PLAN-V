"""Section 19.4: Happy-Path Scenarios H1 through H8."""

import pytest
from app.services.pipeline import PipelineOrchestrator
from core.actions.domain import create_blocks_world_domain, create_gridworld_domain
from core.actions.instantiation import GroundAction
from dynamic.monitor import WorldDeltaMonitor
from dynamic.replanner import DynamicReplanner
from core.contracts import FactSchema
from core.search.algorithms import AStarPlanner, BFSPlanner
from core.verification.verifier import PlanVerifier
from core.world.predicates import Fact
from core.world.problem import SymbolicProblem
from core.world.state import SymbolicState
from core.world.types import ObjectRegistry
from interpretation.vision.detector import DeterministicSceneDetector
from interpretation.vision.scene_generator import SyntheticSceneGenerator


def make_problem(name: str, domain, objects: dict[str, str], init_facts, goal_facts) -> SymbolicProblem:
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
    )


class TestHappyPathScenarios:
    """Verifies all normal operating modes H1 to H8."""

    def test_scenario_h1_simple_valid_planning(self):
        """H1: Simple valid planning problem (1-2 steps)."""
        domain = create_blocks_world_domain()
        init_facts = [
            Fact("on_table", ["b1"]),
            Fact("clear", ["b1"]),
            Fact("handempty", []),
        ]
        goal = [Fact("holding", ["b1"])]
        problem = make_problem("H1_Simple", domain, {"b1": "block"}, init_facts, goal)

        planner = AStarPlanner()
        plan = planner.search(problem, domain)

        assert plan.is_success is True
        assert len(plan.actions) == 1
        assert plan.actions[0].name == "pick_up"
        assert plan.actions[0].arguments == ("b1",)

        verifier = PlanVerifier()
        v_res = verifier.verify(problem, domain, plan)
        assert v_res.is_valid is True

    def test_scenario_h2_multiple_step_planning(self):
        """H2: Multiple-step planning problem."""
        domain = create_blocks_world_domain()
        init_facts = [
            Fact("on_table", ["b1"]),
            Fact("on_table", ["b2"]),
            Fact("clear", ["b1"]),
            Fact("clear", ["b2"]),
            Fact("handempty", []),
        ]
        goal = [Fact("on", ["b1", "b2"])]
        problem = make_problem("H2_MultiStep", domain, {"b1": "block", "b2": "block"}, init_facts, goal)

        planner = AStarPlanner()
        plan = planner.search(problem, domain)

        assert plan.is_success is True
        assert len(plan.actions) == 2
        assert plan.actions[0].name == "pick_up"
        assert plan.actions[1].name == "stack"

        verifier = PlanVerifier()
        v_res = verifier.verify(problem, domain, plan)
        assert v_res.is_valid is True

    def test_scenario_h3_multiple_valid_plans(self):
        """H3: Problem with multiple valid plans."""
        domain = create_blocks_world_domain()
        init_facts = [
            Fact("on_table", ["b1"]),
            Fact("on_table", ["b2"]),
            Fact("clear", ["b1"]),
            Fact("clear", ["b2"]),
            Fact("handempty", []),
        ]
        problem = make_problem(
            "H3_MultiplePaths",
            domain,
            {"b1": "block", "b2": "block"},
            init_facts,
            [Fact("on_table", ["b1"]), Fact("on_table", ["b2"])],
        )

        planner = BFSPlanner()
        plan = planner.search(problem, domain)
        assert plan.is_success is True

        verifier = PlanVerifier()
        v_res = verifier.verify(problem, domain, plan)
        assert v_res.is_valid is True

    def test_scenario_h4_non_trivial_search_sussman_anomaly(self):
        """H4: Problem requiring non-trivial search (Sussman Anomaly)."""
        domain = create_blocks_world_domain()
        init_facts = [
            Fact("on", ["c", "a"]),
            Fact("on_table", ["a"]),
            Fact("on_table", ["b"]),
            Fact("clear", ["c"]),
            Fact("clear", ["b"]),
            Fact("handempty", []),
        ]
        goal = [Fact("on", ["a", "b"]), Fact("on", ["b", "c"])]
        problem = make_problem("H4_Sussman", domain, {"a": "block", "b": "block", "c": "block"}, init_facts, goal)

        planner = AStarPlanner()
        plan = planner.search(problem, domain)

        assert plan.is_success is True
        assert len(plan.actions) == 6

        verifier = PlanVerifier()
        v_res = verifier.verify(problem, domain, plan)
        assert v_res.is_valid is True

    def test_scenario_h5_heuristic_guidance_efficiency(self):
        """H5: A* with RPG heuristic should be efficient."""
        domain = create_blocks_world_domain()
        init_facts = [
            Fact("on", ["c", "a"]),
            Fact("on_table", ["a"]),
            Fact("on_table", ["b"]),
            Fact("clear", ["c"]),
            Fact("clear", ["b"]),
            Fact("handempty", []),
        ]
        goal = [Fact("on", ["a", "b"]), Fact("on", ["b", "c"])]
        problem = make_problem("H5_AStarEfficiency", domain, {"a": "block", "b": "block", "c": "block"}, init_facts, goal)

        astar = AStarPlanner()
        plan_astar = astar.search(problem, domain)
        assert plan_astar.is_success is True
        assert plan_astar.nodes_expanded > 0

    def test_scenario_h6_natural_language_to_verified_plan(self):
        """H6: Natural-language instruction -> symbolic problem -> plan."""
        orchestrator = PipelineOrchestrator()
        prompt = "Move the red box next to the blue box. Do not move the glass."
        res = orchestrator.run(prompt=prompt, algorithm="A*")

        assert res.validation.is_valid is True
        assert res.candidate_plan.is_success is True
        assert res.initial_verification.is_valid is True
        assert res.final_plan is not None
        assert len(res.final_plan.actions) > 0

    def test_scenario_h7_visual_observation_to_plan(self):
        """H7: Visual observation -> symbolic world state -> plan."""
        gen = SyntheticSceneGenerator(width=400, height=400)
        blocks = [
            {"name": "red_box", "color": "red", "shape": "box"},
            {"name": "blue_box", "color": "blue", "shape": "box"},
        ]
        scene = gen.generate_tabletop_scene(blocks)

        detector = DeterministicSceneDetector()
        detected = detector.detect(scene.image)
        assert len(detected.detected_objects) >= 2

        orchestrator = PipelineOrchestrator()
        res = orchestrator.run(
            prompt="Stack the red box on the blue box.",
            image=scene.image,
            algorithm="A*",
        )
        assert res.has_image is True
        assert res.final_plan is not None
        assert res.final_verification.is_valid is True

    def test_scenario_h8_dynamic_environment_reactive_replanning(self):
        """H8: Dynamic environment -> plan invalidation -> replanning."""
        domain = create_blocks_world_domain()
        init_facts = [
            Fact("on_table", ["b1"]),
            Fact("on_table", ["b2"]),
            Fact("clear", ["b1"]),
            Fact("clear", ["b2"]),
            Fact("handempty", []),
        ]
        goal = [Fact("on", ["b1", "b2"])]
        problem = make_problem("H8_Dynamic", domain, {"b1": "block", "b2": "block"}, init_facts, goal)

        planner = AStarPlanner()
        plan = planner.search(problem, domain)
        assert plan.is_success is True

        # External perturbation: b1 is suddenly held by someone else, invalidating the plan
        replanner = DynamicReplanner()
        new_obs = [
            FactSchema(predicate="holding", arguments=("b1",)),
            FactSchema(predicate="on_table", arguments=("b2",)),
            FactSchema(predicate="clear", arguments=("b2",)),
        ]
        replan_triggered, active_plan, delta = replanner.process_observation(
            current_state=problem.initial_state,
            remaining_plan=plan,
            problem=problem,
            domain=domain,
            new_observation_facts=new_obs,
        )
        assert replan_triggered is True
        assert delta.is_plan_invalidating is True
        assert active_plan is not None
        assert active_plan.is_success is True

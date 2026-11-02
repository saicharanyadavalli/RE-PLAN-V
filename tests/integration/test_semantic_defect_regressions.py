"""Targeted Regression Tests for Semantic Defect Corrections (TC-13, TC-15, TC-16)."""

import pytest
from app.services.pipeline import PipelineOrchestrator
from core.contracts import TaskConstraintType
from interpretation.router import DomainRouter, RoutingOutcome
from core.domains import registry


@pytest.fixture
def orchestrator() -> PipelineOrchestrator:
    return PipelineOrchestrator()


@pytest.fixture
def router() -> DomainRouter:
    return DomainRouter(registry=registry)


class TestSemanticDefectRegressions:
    """Verifies that the targeted semantic defects are permanently resolved."""

    def test_tc13_household_robotics_forbid_bedroom_navigation(
        self, router: DomainRouter, orchestrator: PipelineOrchestrator
    ):
        prompt = "Could you move the mug from the office desk to the kitchen shelf, and please never enter the bedroom?"

        # 1. Router verification
        route_res = router.route(prompt)
        assert route_res.outcome == RoutingOutcome.SUPPORTED
        assert route_res.selected_domain_id == "household_robotics"

        # Check typed constraint mapping
        assert len(route_res.typed_constraints) >= 1
        tc = route_res.typed_constraints[0]
        assert tc.constraint_type == TaskConstraintType.FORBID_TRANSITION
        assert tc.action_name in ("navigate_room", "navigate")
        assert tc.to_entity == "bedroom"
        assert tc.arg_index == 2

        # 2. End-to-end pipeline execution
        result = orchestrator.run(prompt=prompt, algorithm="A*", domain_id="auto")
        assert result.validation.is_valid is True
        assert result.final_verification.is_valid is True
        assert result.final_plan is not None
        assert len(result.final_plan.actions) > 0

        # Verify no action in the plan enters bedroom
        for act in result.final_plan.actions:
            if act.name in ("navigate_room", "navigate"):
                assert "bedroom" not in act.arguments, f"Robot entered bedroom in action: {act}"
            assert act.arguments[-1] != "bedroom"

        # Verify goal achievement
        action_names = [a.name for a in result.final_plan.actions]
        assert "pick_from_surface" in action_names
        assert "place_on_surface" in action_names

    def test_tc15_scheduling_precedence_ordering(
        self, router: DomainRouter, orchestrator: PipelineOrchestrator
    ):
        prompt = "Please schedule design_review before code_review on machine_1."

        # 1. Router verification
        route_res = router.route(prompt)
        assert route_res.outcome == RoutingOutcome.SUPPORTED
        assert route_res.selected_domain_id == "scheduling"

        # Check precedence fact exists in initial state
        has_precedence = any(
            f.predicate == "precedes"
            and f.arguments == ("design_review", "code_review")
            for f in route_res.initial_facts
        )
        assert has_precedence is True

        # 2. End-to-end pipeline execution
        result = orchestrator.run(prompt=prompt, algorithm="A*", domain_id="auto")
        assert result.validation.is_valid is True
        assert result.final_verification.is_valid is True
        assert result.final_plan is not None

        # Verify plan actions
        actions = result.final_plan.actions
        assert len(actions) >= 2

        # design_review must be scheduled before code_review
        # schedule_independent_job schedules its first argument (design_review)
        # schedule_dependent_job schedules its second argument (code_review) dependent on the first (design_review)
        design_idx = next(
            (i for i, a in enumerate(actions) if a.name == "schedule_independent_job" and a.arguments[0] == "design_review"),
            -1,
        )
        code_idx = next(
            (i for i, a in enumerate(actions) if a.name == "schedule_dependent_job" and a.arguments[1] == "code_review"),
            -1,
        )

        assert design_idx != -1, f"design_review was not scheduled via schedule_independent_job: {actions}"
        assert code_idx != -1, f"code_review was not scheduled via schedule_dependent_job: {actions}"
        assert design_idx < code_idx, f"design_review (step {design_idx}) must precede code_review (step {code_idx})"

        # Verify code_review used schedule_dependent_job with design_review as dependency
        code_act = actions[code_idx]
        assert code_act.name == "schedule_dependent_job"
        assert code_act.arguments[0] == "design_review"
        assert code_act.arguments[1] == "code_review"

    def test_tc16_software_workflow_staging_environment_extraction(
        self, router: DomainRouter, orchestrator: PipelineOrchestrator
    ):
        prompt = "Please build, test, scan, and deploy release_v1 to staging."

        # 1. Router verification
        route_res = router.route(prompt)
        assert route_res.outcome == RoutingOutcome.SUPPORTED
        assert route_res.selected_domain_id == "software_workflow"
        assert "staging" in route_res.entities
        assert route_res.entities["staging"] == "environment"
        assert "test" not in route_res.entities or route_res.entities["test"] != "environment"

        # Goal must target staging
        has_deploy_staging = any(
            f.predicate == "deployed_to" and "staging" in f.arguments
            for f in route_res.goal_facts
        )
        assert has_deploy_staging is True

        # 2. End-to-end pipeline execution
        result = orchestrator.run(prompt=prompt, algorithm="A*", domain_id="auto")
        assert result.validation.is_valid is True
        assert result.final_verification.is_valid is True
        assert result.final_plan is not None
        assert len(result.final_plan.actions) == 5

        # Verify action sequence
        action_names = [a.name for a in result.final_plan.actions]
        expected_actions = {
            "run_unit_tests",
            "run_security_scan",
            "build_artifact",
            "grant_approval",
            "deploy_to_environment",
        }
        assert set(action_names) == expected_actions

        # Check deployment target in final action
        deploy_act = result.final_plan.actions[-1]
        assert deploy_act.name == "deploy_to_environment"
        assert "staging" in deploy_act.arguments

    def test_tc16_software_workflow_production_environment_extraction(
        self, router: DomainRouter, orchestrator: PipelineOrchestrator
    ):
        prompt = "Please build, test, scan, and deploy release_v1 to production."

        route_res = router.route(prompt)
        assert route_res.outcome == RoutingOutcome.SUPPORTED
        assert route_res.selected_domain_id == "software_workflow"
        assert "production" in route_res.entities
        assert route_res.entities["production"] == "environment"

        result = orchestrator.run(prompt=prompt, algorithm="A*", domain_id="auto")
        assert result.validation.is_valid is True
        assert result.final_verification.is_valid is True
        assert result.final_plan is not None
        deploy_act = result.final_plan.actions[-1]
        assert "production" in deploy_act.arguments

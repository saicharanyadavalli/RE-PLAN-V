"""Software Automation and CI/CD Workflow Planning Domain."""

from __future__ import annotations

from typing import Any, Dict, List
from core.actions.definition import ActionDefinition, ActionParameter
from core.domains.base import BaseDomain
from core.world.predicates import Fact, PredicateDefinition
from core.world.types import TypeHierarchy


class SoftwareWorkflowDomain(BaseDomain):
    """Abstract symbolic CI/CD workflow, software testing, and deployment orchestration domain.

    NOTE: Generates plans only. NEVER dispatches shell execution or remote cloud mutations.
    """

    def __init__(self) -> None:
        th = TypeHierarchy()
        th.add_type("commit", "object")
        th.add_type("artifact", "object")
        th.add_type("environment", "object")

        preds = [
            PredicateDefinition("code_checked_out", ["commit"]),
            PredicateDefinition("tests_passed", ["commit"]),
            PredicateDefinition("security_scanned", ["commit"]),
            PredicateDefinition("artifact_built", ["artifact", "commit"]),
            PredicateDefinition("approval_granted", ["environment", "commit"]),
            PredicateDefinition("deployed_to", ["artifact", "environment"]),
            PredicateDefinition("environment_healthy", ["environment"]),
        ]

        run_tests = ActionDefinition(
            name="run_unit_tests",
            parameters=[ActionParameter("c", "commit")],
            preconditions=[Fact("code_checked_out", ["?c"])],
            add_effects=[Fact("tests_passed", ["?c"])],
            del_effects=[],
            cost=1.0,
            description="Execute automated test suite against the target commit",
        )

        run_scan = ActionDefinition(
            name="run_security_scan",
            parameters=[ActionParameter("c", "commit")],
            preconditions=[Fact("code_checked_out", ["?c"])],
            add_effects=[Fact("security_scanned", ["?c"])],
            del_effects=[],
            cost=1.0,
            description="Run static security and vulnerability audit over source files",
        )

        build_art = ActionDefinition(
            name="build_artifact",
            parameters=[ActionParameter("c", "commit"), ActionParameter("art", "artifact")],
            preconditions=[
                Fact("code_checked_out", ["?c"]),
                Fact("tests_passed", ["?c"]),
            ],
            add_effects=[Fact("artifact_built", ["?art", "?c"])],
            del_effects=[],
            cost=2.0,
            description="Compile binaries and container image package from verified commit",
        )

        grant_appr = ActionDefinition(
            name="grant_approval",
            parameters=[ActionParameter("c", "commit"), ActionParameter("env", "environment")],
            preconditions=[
                Fact("tests_passed", ["?c"]),
                Fact("security_scanned", ["?c"]),
            ],
            add_effects=[Fact("approval_granted", ["?env", "?c"])],
            del_effects=[],
            cost=0.5,
            description="Sign off production deployment approval gate after test and security verification",
        )

        deploy_env = ActionDefinition(
            name="deploy_to_environment",
            parameters=[
                ActionParameter("c", "commit"),
                ActionParameter("art", "artifact"),
                ActionParameter("env", "environment"),
            ],
            preconditions=[
                Fact("artifact_built", ["?art", "?c"]),
                Fact("approval_granted", ["?env", "?c"]),
                Fact("environment_healthy", ["?env"]),
            ],
            add_effects=[Fact("deployed_to", ["?art", "?env"])],
            del_effects=[],
            cost=1.5,
            description="Deploy compiled artifact into the target environment",
        )

        examples = [
            {
                "prompt": "Build, test, scan, and deploy release_v1 to staging.",
                "domain": "software_workflow",
                "goal": "deployed_to(pkg_v1, staging)",
            },
            {
                "prompt": "Require security approval before deploying artifact_prod to production environment.",
                "domain": "software_workflow",
                "goal": "deployed_to(artifact_prod, production)",
            },
        ]

        super().__init__(
            domain_id="software_workflow",
            name="Software Automation / CI/CD Workflow",
            version="1.0.0",
            description="Symbolic software release pipeline, testing gates, approval sign-offs, and multi-stage deployment planning.",
            type_hierarchy=th,
            predicates=preds,
            actions=[run_tests, run_scan, build_art, grant_appr, deploy_env],
            default_invariants=[],
            task_examples=examples,
            supported_patterns=[
                "build", "test", "deploy", "staging", "production", "artifact", "commit", "release", "ci/cd", "workflow", "scan"
            ],
            unsupported_features=[
                "live remote shell execution", "cloud credential modification", "direct production network access"
            ],
        )

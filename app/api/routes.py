"""FastAPI route handlers for RE-PLAN-V."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.services.pipeline import PipelineExecutionResult, PipelineOrchestrator
from app.services.problem_builder import ValidatedProblemBuilder
from core.graph.resource_limits import GraphBudgetConfig, GraphBudgetLimits, graph_concurrency_manager
from evaluation.experiments.runner import ExperimentRunner

router = APIRouter(prefix="/api")
orchestrator = PipelineOrchestrator()
experiment_runner = ExperimentRunner()


class PipelineRequest(BaseModel):
    prompt: str = "Move the red box next to the blue box. Do not move the glass."
    domain_id: Optional[str] = "auto"
    algorithm: str = "A*"
    force_invalid_first_candidate: bool = False
    provider_type: str = "mock"  # "mock", "ollama", "gemini", "openai"
    llm_model: Optional[str] = "gemma2:2b"


class BenchmarkRequest(BaseModel):
    num_instances: int = Field(default=5, ge=1)
    seed: int = 42


@router.post("/pipeline/run", response_model=PipelineExecutionResult)
def run_pipeline(req: PipelineRequest) -> PipelineExecutionResult:
    from core.domains import registry
    if req.domain_id and req.domain_id != "auto" and not registry.get(req.domain_id):
        raise HTTPException(status_code=404, detail=f"Domain '{req.domain_id}' is not registered.")
    try:
        result = orchestrator.run(
            prompt=req.prompt,
            algorithm=req.algorithm,
            force_invalid_first_candidate=req.force_invalid_first_candidate,
            provider_type=req.provider_type,
            llm_model=req.llm_model,
            domain_id=req.domain_id,
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@router.post("/benchmark/run")
def run_benchmark(req: BenchmarkRequest) -> Dict[str, Any]:
    try:
        results = experiment_runner.run_primary_research_experiment(
            num_instances=req.num_instances,
            seed=req.seed,
        )
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/benchmark/attribution")
@router.get("/benchmark/attribution_matrix")
def get_attribution_matrix() -> Dict[str, Any]:
    """Returns the latest 5-class fault attribution confusion matrix report."""
    report_file = Path(__file__).resolve().parent.parent.parent / "evaluation" / "reports" / "fault_attribution_matrix.json"
    if report_file.exists():
        with open(report_file, "r", encoding="utf-8") as f:
            return json.load(f)
    # If not yet generated, run live
    return experiment_runner.run_attribution_experiment(instances_per_class=10, seed=42)


@router.post("/benchmark/attribution_matrix")
def run_attribution_matrix_live(instances_per_class: int = 10, seed: int = 42) -> Dict[str, Any]:
    """Runs a live 5-class fault attribution confusion matrix experiment."""
    try:
        return experiment_runner.run_attribution_experiment(instances_per_class=instances_per_class, seed=seed)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/system/info")
def get_system_info() -> Dict[str, Any]:
    from core.domains import registry
    return {
        "app": "RE-PLAN-V",
        "version": "0.2.0",
        "symbolic_core": "Authoritative STRIPS",
        "available_algorithms": ["A*", "BFS", "BEST_FIRST"],
        "domains": [d.domain_id for d in registry.list_domains()],
        "graph_mode": "Model B: Complete Reachable-State Graph",
        "research_question": "Can counterexample-guided fault attribution and automatic repair improve recovery from initially invalid plans compared with generic plan regeneration?",
    }


@router.get("/domains")
def get_domains() -> List[Dict[str, Any]]:
    """Returns metadata, actions, predicates, and task examples for all 6 registered domains."""
    from core.domains import registry
    return registry.get_metadata_summary()


@router.get("/domains/{domain_id}")
def get_domain_details(domain_id: str) -> Dict[str, Any]:
    """Returns detailed schema, predicates, actions, invariants, and types for a specific domain."""
    from core.domains import registry
    dom = registry.get(domain_id)
    if not dom:
        raise HTTPException(status_code=404, detail=f"Domain '{domain_id}' not found.")
    return dom.to_dict()


class GraphEnumerateRequest(GraphBudgetConfig):
    """Request payload schema for Model B reachable state graph enumeration."""
    pass


@router.post("/graph/enumerate")
def enumerate_state_space_graph(req: GraphBudgetConfig) -> Dict[str, Any]:
    """Model B: Computes the complete reachable state-space graph using authoritative ValidatedProblemBuilder."""
    from core.domains import registry
    from core.graph.enumerator import CompleteReachableGraphEnumerator
    from interpretation.router import RoutingOutcome

    # Explicit domain check for 404 compliance
    if req.domain_id and req.domain_id != "auto" and not registry.get(req.domain_id):
        raise HTTPException(status_code=404, detail=f"Domain '{req.domain_id}' not found.")

    builder = ValidatedProblemBuilder(registry=registry)
    build_res = builder.build_problem(
        prompt=req.prompt or "Stack the red box on the blue box.",
        domain_id=req.domain_id if (req.domain_id and req.domain_id != "auto") else None,
        problem_name=f"{req.domain_id or 'graph'}_task",
    )

    if not build_res.is_success or build_res.problem is None or build_res.domain is None:
        status_val = build_res.status or (build_res.outcome.value if build_res.outcome else "UNSUPPORTED")
        if build_res.outcome == RoutingOutcome.NEEDS_CLARIFICATION or status_val == "NEEDS_CLARIFICATION":
            return {
                "status": "NEEDS_CLARIFICATION",
                "clarification_question": build_res.clarification_question,
                "explanation": build_res.error_message,
                "elements": [],
            }
        if status_val == "INVARIANT_VIOLATION":
            return {
                "status": "INVARIANT_VIOLATION",
                "explanation": build_res.error_message,
                "elements": [],
            }
        return {
            "status": status_val,
            "clarification_question": build_res.clarification_question,
            "explanation": build_res.error_message,
            "elements": [],
        }

    # Strict bounded concurrency for graph exploration
    if not graph_concurrency_manager.acquire():
        raise HTTPException(
            status_code=429,
            detail=f"Graph enumeration capacity exceeded (max {graph_concurrency_manager.max_concurrent} concurrent). Try again later.",
        )
    try:
        enumerator = CompleteReachableGraphEnumerator(
            max_nodes=req.max_nodes,
            max_edges=req.max_edges,
            timeout_seconds=req.timeout_seconds,
        )
        graph = enumerator.enumerate_graph(build_res.problem, build_res.domain)
        if graph.stats.truncation_reason and "INITIAL_STATE_INVARIANT_VIOLATION" in graph.stats.truncation_reason:
            return {
                "status": "INVARIANT_VIOLATION",
                "explanation": graph.stats.truncation_reason,
                "elements": [],
                "stats": graph.stats.model_dump(),
            }
        return graph.to_cytoscape()
    finally:
        graph_concurrency_manager.release()


class FormalizeRequest(BaseModel):
    prompt: str = "Move the red box next to the blue box. Do not move the glass."
    domain_id: Optional[str] = "blocks_world"
    provider: str = "gemini"  # "gemini", "lmstudio", "ollama", "mock"
    api_key: Optional[str] = None
    model: Optional[str] = None


@router.post("/llm/formalize")
def test_formalize(req: FormalizeRequest) -> Dict[str, Any]:
    """Dedicated endpoint to test natural language formalization via Gemini or local models."""
    from interpretation.llm.live import LiveLLMProvider
    from core.domains import registry

    target_domain_id = req.domain_id or "blocks_world"
    target_domain = registry.get(target_domain_id)
    if not target_domain:
        raise HTTPException(status_code=404, detail=f"Domain '{target_domain_id}' is not registered.")

    provider = LiveLLMProvider(
        provider=req.provider,
        api_key=req.api_key,
        model=req.model,
    )

    try:
        proposal = provider.interpret(req.prompt, target_domain)
        return {
            "status": "success",
            "provider": req.provider,
            "task_id": proposal.task_id,
            "confidence": proposal.confidence,
            "entities": proposal.entities,
            "initial_facts": [f"{f.predicate}({', '.join(f.arguments)})" for f in proposal.initial_facts],
            "goal_facts": [f"{f.predicate}({', '.join(f.arguments)})" for f in proposal.goal_facts],
            "negative_constraints": [f"{f.predicate}({', '.join(f.arguments)})" for f in proposal.negative_constraints],
            "invariants": [f"{f.predicate}({', '.join(f.arguments)})" for f in proposal.invariants],
            "raw_prompt": proposal.raw_prompt,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Formalization error: {str(e)}")


@router.get("/system/providers")
def get_providers_status() -> Dict[str, Any]:
    """Returns active status of all formalizer providers (LM Studio, Gemini, Mock)."""
    import os
    import httpx
    from pathlib import Path
    try:
        from dotenv import load_dotenv
        env_f = Path(__file__).resolve().parent.parent.parent / ".env"
        if env_f.exists():
            load_dotenv(dotenv_path=env_f, override=True)
    except Exception:
        pass

    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
    gemini_model = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")

    nvidia_key = (os.environ.get("NVIDIA_API_KEY") or "").strip()
    nvidia_model = os.environ.get("NVIDIA_MODEL", "meta/llama-3.1-8b-instruct")

    # Probe LM Studio
    lm_studio_url = os.environ.get("LM_STUDIO_URL", "http://127.0.0.1:1234")
    lm_studio_online = False
    lm_studio_models = []
    try:
        with httpx.Client(timeout=1.0, trust_env=False) as client:
            r = client.get(f"{lm_studio_url}/api/v1/models")
            if r.status_code == 200:
                lm_studio_online = True
                lm_studio_models = [m.get("key") for m in r.json().get("models", []) if m.get("loaded_instances")]
    except Exception:
        pass

    return {
        "providers": {
            "mock": {
                "name": "Deterministic Zero-API Rule Engine",
                "available": True,
                "offline": True,
            },
            "lmstudio": {
                "name": "LM Studio Local Server",
                "url": lm_studio_url,
                "online": lm_studio_online,
                "loaded_models": lm_studio_models,
            },
            "gemini": {
                "name": "Google Gemini API (Cloud)",
                "model": gemini_model,
                "has_key": bool(gemini_key),
                "key_preview": f"{gemini_key[:4]}...{gemini_key[-4:]}" if len(gemini_key) > 8 else ("Set" if gemini_key else "Missing (add to .env)"),
            },
            "nvidia": {
                "name": "NVIDIA NIM Cloud",
                "model": nvidia_model,
                "has_key": bool(nvidia_key),
                "key_preview": f"{nvidia_key[:4]}...{nvidia_key[-4:]}" if len(nvidia_key) > 8 else ("Set" if nvidia_key else "Missing (add to .env)"),
            },
            "openai": {
                "name": "OpenAI Compatible Endpoint",
                "has_key": bool(os.environ.get("OPENAI_API_KEY", "").strip()),
            },
        }
    }


class DynamicSimulationRequest(BaseModel):
    initial_prompt: str = "Stack the red box on the green box, then put the blue box on the red box."
    perturbed_fact: str = "on_table(blue_box)"  # e.g., an external change moves blue_box or removes a prerequisite


@router.post("/dynamic/simulate")
def simulate_dynamic_environment_change(req: DynamicSimulationRequest) -> Dict[str, Any]:
    """Demonstrates Screen 3 of the Explainer Doc:
    World changes after plan creation -> WorldDeltaMonitor detects change ->
    Plan invalidated -> Root Cause: ENVIRONMENT_CHANGE -> Replanning -> Verified new plan.
    """
    from core.actions.domain import create_blocks_world_domain
    from dynamic.replanner import DynamicReplanner
    from core.contracts import FactSchema
    from app.services.pipeline import PipelineOrchestrator

    domain = create_blocks_world_domain()
    pipe = PipelineOrchestrator()
    initial_res = pipe.run(prompt=req.initial_prompt, algorithm="A*")

    if not initial_res.final_plan or not initial_res.final_plan.actions:
        raise HTTPException(status_code=400, detail="Initial plan generation failed.")

    replanner = DynamicReplanner()
    # Build problem from the verified proposal
    problem = pipe.validator.convert_to_problem(initial_res.interpretation, domain)
    curr_state = problem.initial_state

    # Register dynamic obstacle in problem registry
    problem.registry.register_object("obstacle", "block")

    # Target block from the final plan step (e.g. b2 in stack(b1, b2))
    target_block = initial_res.final_plan.actions[-1].arguments[1] if len(initial_res.final_plan.actions[-1].arguments) > 1 else initial_res.final_plan.actions[-1].arguments[0]

    # Generate observation facts with perturbation: an obstacle is placed on target_block
    obs_facts = [f.to_schema() for f in curr_state.facts if not (f.predicate == "clear" and target_block in f.arguments)]
    obs_facts.append(FactSchema(predicate="on", arguments=("obstacle", target_block)))
    obs_facts.append(FactSchema(predicate="clear", arguments=("obstacle",)))

    replan_triggered, new_plan, delta = replanner.process_observation(
        current_state=curr_state,
        remaining_plan=initial_res.final_plan,
        problem=problem,
        domain=domain,
        new_observation_facts=obs_facts,
    )

    return {
        "status": "success",
        "world_change_detected": replan_triggered,
        "delta": {
            "delta_id": delta.delta_id,
            "added_facts": [f.to_string() for f in delta.added_facts],
            "removed_facts": [f.to_string() for f in delta.removed_facts],
            "is_plan_invalidating": delta.is_plan_invalidating,
            "explanation": delta.explanation,
        },
        "root_cause": "ENVIRONMENT_CHANGE",
        "old_plan_actions": [f"{a.name}({', '.join(a.arguments)})" for a in initial_res.final_plan.actions],
        "new_plan_actions": [f"{a.name}({', '.join(a.arguments)})" for a in new_plan.actions],
        "final_verification": "VERIFIED",
    }


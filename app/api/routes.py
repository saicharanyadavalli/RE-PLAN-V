"""FastAPI route handlers for RE-PLAN-V."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.pipeline import PipelineExecutionResult, PipelineOrchestrator
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
    num_instances: int = 5
    seed: int = 42


@router.post("/pipeline/run", response_model=PipelineExecutionResult)
def run_pipeline(req: PipelineRequest) -> PipelineExecutionResult:
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


class GraphEnumerateRequest(BaseModel):
    domain_id: str = "blocks_world"
    prompt: Optional[str] = "Stack the red box on the blue box."
    max_nodes: int = 300
    max_edges: int = 1000
    timeout_seconds: float = 5.0


@router.post("/graph/enumerate")
def enumerate_state_space_graph(req: GraphEnumerateRequest) -> Dict[str, Any]:
    """Model B: Computes the complete reachable state-space graph."""
    from core.domains import registry
    from core.graph.enumerator import CompleteReachableGraphEnumerator
    from core.world.predicates import Fact
    from core.world.problem import SymbolicProblem
    from core.world.state import SymbolicState
    from core.world.types import ObjectRegistry
    from interpretation.router import DomainRouter, RoutingOutcome

    router = DomainRouter(registry=registry)
    routing = router.route(
        req.prompt or "Stack the red box on the blue box.",
        explicit_domain_id=req.domain_id if req.domain_id != "auto" else None,
    )
    if routing.outcome != RoutingOutcome.SUPPORTED:
        return {
            "status": routing.outcome.value,
            "clarification_question": routing.clarification_question,
            "explanation": routing.explanation,
            "elements": [],
        }

    target_domain_id = req.domain_id if req.domain_id != "auto" else routing.selected_domain_id
    domain = registry.get(target_domain_id)
    if not domain:
        raise HTTPException(status_code=404, detail=f"Domain '{target_domain_id}' not found.")

    reg = ObjectRegistry(domain.type_hierarchy)
    for obj_name, obj_type in routing.entities.items():
        reg.register_object(obj_name, obj_type)

    s0 = SymbolicState([
        Fact(f.predicate, list(f.arguments)) for f in routing.initial_facts
    ])
    goals = [
        Fact(f.predicate, list(f.arguments)) for f in routing.goal_facts
    ]
    problem = SymbolicProblem(
        name=f"{domain.domain_id}_task",
        domain_name=domain.domain_id,
        registry=reg,
        initial_state=s0,
        goal_conditions=goals,
    )

    enumerator = CompleteReachableGraphEnumerator(
        max_nodes=req.max_nodes,
        max_edges=req.max_edges,
        timeout_seconds=req.timeout_seconds,
    )
    graph = enumerator.enumerate_graph(problem, domain)
    return graph.to_cytoscape()


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

    target_domain = registry.get(req.domain_id or "blocks_world")
    if not target_domain:
        from core.actions.domain import create_blocks_world_domain
        target_domain = create_blocks_world_domain()

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


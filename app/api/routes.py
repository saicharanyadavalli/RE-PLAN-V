"""FastAPI route handlers for RE-PLAN-V."""

from __future__ import annotations

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


@router.get("/system/info")
def get_system_info() -> Dict[str, Any]:
    return {
        "app": "RE-PLAN-V",
        "version": "0.1.0",
        "symbolic_core": "Authoritative STRIPS",
        "available_algorithms": ["A*", "BFS", "BEST_FIRST"],
        "domains": ["blocks_world", "gridworld"],
        "research_question": "Can counterexample-guided fault attribution and automatic repair improve recovery from initially invalid plans compared with generic plan regeneration?",
    }


class FormalizeRequest(BaseModel):
    prompt: str = "Move the red box next to the blue box. Do not move the glass."
    provider: str = "gemini"  # "gemini", "lmstudio", "ollama", "mock"
    api_key: Optional[str] = None
    model: Optional[str] = None


@router.post("/llm/formalize")
def test_formalize(req: FormalizeRequest) -> Dict[str, Any]:
    """Dedicated endpoint to test natural language formalization via Gemini or local models."""
    from interpretation.llm.live import LiveLLMProvider
    from core.actions.domain import create_blocks_world_domain

    domain = create_blocks_world_domain()
    provider = LiveLLMProvider(
        provider=req.provider,
        api_key=req.api_key,
        model=req.model,
    )

    try:
        proposal = provider.interpret(req.prompt, domain)
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

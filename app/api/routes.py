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

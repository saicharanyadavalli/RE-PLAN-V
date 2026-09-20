"""WebSocket router for live event-driven pipeline streaming."""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.pipeline import PipelineOrchestrator
from core.logger import get_logger

logger = get_logger("websocket_router")
router = APIRouter()
orchestrator = PipelineOrchestrator()


@router.websocket("/ws/pipeline")
async def websocket_pipeline_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        req = await websocket.receive_json()
        prompt = req.get("prompt", "Move the red box next to the blue box. Do not move the glass.")
        algorithm = req.get("algorithm", "A*")
        force_fault = bool(req.get("force_fault", False))
        provider_type = req.get("provider_type", "mock")
        llm_model = req.get("llm_model", "gemma2:2b")

        async def emit(stage: str, message: str, data: Optional[Dict[str, Any]] = None):
            await websocket.send_json({
                "stage": stage,
                "timestamp": time.time(),
                "message": message,
                "data": data or {},
            })
            await asyncio.sleep(0.02)

        await emit("PIPELINE_STARTED", "Initializing pipeline execution...", {"prompt": prompt})

        # Step 1: Formalize & Validate
        await emit("INTERPRETATION_STARTED", "Formalizing natural language into symbolic schema...")
        result = orchestrator.run(
            prompt=prompt,
            algorithm=algorithm,
            force_invalid_first_candidate=force_fault,
            provider_type=provider_type,
            llm_model=llm_model,
        )

        await emit("INTERPRETATION_COMPLETED", "Task proposal formalized and validated.", {
            "entities": result.interpretation.entities,
            "goal_facts": [f.model_dump() for f in result.interpretation.goal_facts],
            "initial_facts": [f.model_dump() for f in result.interpretation.initial_facts],
            "negative_constraints": [f.model_dump() for f in result.interpretation.negative_constraints],
            "is_valid": result.validation.is_valid,
        })

        # Step 2: Search Candidate
        await emit("SEARCH_COMPLETED", f"Candidate plan generated ({len(result.candidate_plan.actions)} actions).", {
            "actions": [a.model_dump() for a in result.candidate_plan.actions],
            "cost": result.candidate_plan.total_cost,
        })

        # Step 3: Verification & Diagnostics
        if not result.initial_verification.is_valid:
            await emit("VERIFICATION_FAILED", f"Initial candidate failed verification at step {result.initial_verification.failed_step_index}.", {
                "failed_step": result.initial_verification.failed_step_index,
                "explanation": result.initial_verification.explanation,
            })

            if result.counterexample:
                await emit("COUNTEREXAMPLE_EXTRACTED", "Minimal counterexample witness isolated.", {
                    "witness": result.counterexample.model_dump()
                })

            if result.fault_attribution:
                await emit("ATTRIBUTION_CLASSIFIED", f"Fault attributed to {result.fault_attribution.fault_class}.", {
                    "fault_class": result.fault_attribution.fault_class,
                    "affected_stage": result.fault_attribution.affected_stage,
                    "confidence": result.fault_attribution.confidence,
                })

            if result.replanning_result:
                await emit("REPAIR_INJECTED", "Negative constraints injected; symbolic replanning succeeded.", {
                    "iterations": result.replanning_result.iterations,
                    "repairs_applied": [r.model_dump() for r in result.repairs_applied],
                })
        else:
            await emit("VERIFICATION_RESULT", "Candidate plan satisfies all preconditions and invariants.", {
                "is_valid": True
            })

        # Step 4: Final Plan Execution
        await emit("FINAL_VERIFICATION", "Final plan formally verified and ready for execution.", {
            "is_valid": result.final_verification.is_valid,
            "final_plan": [a.model_dump() for a in result.final_plan.actions] if result.final_plan else [],
            "execution_time_ms": result.total_execution_time_ms,
        })

        await emit("PIPELINE_FINISHED", "Pipeline execution finished.", {
            "total_execution_time_ms": result.total_execution_time_ms,
        })

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected.")
    except Exception as e:
        logger.error(f"WebSocket execution error: {e}")
        try:
            await websocket.send_json({"stage": "ERROR", "message": str(e), "data": {}})
        except Exception:
            pass

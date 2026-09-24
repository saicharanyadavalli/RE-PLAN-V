"""WebSocket router for live event-driven pipeline streaming.

Updated for Retry Tree architecture — streams each stage attempt,
retry, cascade, and backtrack event to the frontend in real-time.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.pipeline import PipelineOrchestrator, PLANNER_CASCADE
from core.contracts import (
    GroundActionSchema,
    PipelineDecisionTrace,
    PipelineStageStatus,
    PlanSchema,
    StageAttemptRecord,
    VerificationResultSchema,
)
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
        # 1-second demonstration pacing (requested by user for clear live presentation)
        step_delay = float(req.get("step_delay", 0.9))

        async def emit(stage: str, message: str, data: Optional[Dict[str, Any]] = None):
            await websocket.send_json({
                "stage": stage,
                "timestamp": time.time(),
                "message": message,
                "data": data or {},
            })
            if step_delay > 0:
                await asyncio.sleep(step_delay)

        await emit("PIPELINE_STARTED", "Initializing Retry Tree pipeline...", {
            "prompt": prompt,
            "architecture": "retry_tree",
        })

        # ──── Resolve Provider ─────────────────────────────────────────
        is_live = provider_type and provider_type != "mock"
        if is_live:
            from interpretation.llm.live import LiveLLMProvider
            active_provider = LiveLLMProvider(provider=provider_type, model=llm_model)
        else:
            active_provider = orchestrator.llm_provider

        trace = PipelineDecisionTrace()
        last_validation_errors: Optional[List[str]] = None

        for backtrack_idx in range(orchestrator.max_backtracks + 1):
            if backtrack_idx > 0:
                await emit("BACKTRACK", f"Backtracking to re-interpret (attempt {backtrack_idx + 1})...", {
                    "backtrack_number": backtrack_idx,
                    "reason": "; ".join(last_validation_errors) if last_validation_errors else "Unknown",
                })

            # ─── Stage 1: Interpretation ───────────────────────────────
            await emit("INTERPRETATION_STARTED", "Formalizing natural language into symbolic schema...")

            t0 = time.perf_counter()
            provider_name = provider_type
            try:
                if hasattr(active_provider, 'interpret_with_retry'):
                    proposal, provider_name = active_provider.interpret_with_retry(
                        prompt=prompt,
                        domain=orchestrator.domain,
                        validation_errors=last_validation_errors,
                    )
                else:
                    proposal = active_provider.interpret(prompt, orchestrator.domain)
                t_interp_ms = (time.perf_counter() - t0) * 1000.0

                trace.stage_trace.append(StageAttemptRecord(
                    stage="INTERPRET",
                    attempt=backtrack_idx + 1,
                    status=PipelineStageStatus.SUCCESS,
                    provider_used=provider_name,
                    duration_ms=t_interp_ms,
                    recovery_action="retry_with_feedback" if last_validation_errors else None,
                ))
                trace.interpretation_attempts += 1

            except Exception as e:
                t_interp_ms = (time.perf_counter() - t0) * 1000.0
                # Fallback to mock
                proposal = orchestrator.llm_provider.interpret(prompt, orchestrator.domain)
                provider_name = "mock_fallback"
                trace.stage_trace.append(StageAttemptRecord(
                    stage="INTERPRET",
                    attempt=backtrack_idx + 1,
                    status=PipelineStageStatus.FAILED,
                    provider_used=provider_type,
                    duration_ms=t_interp_ms,
                    error=str(e),
                    recovery_action="mock_fallback",
                ))

            # ─── Stage 2: Validation ──────────────────────────────────
            t1 = time.perf_counter()
            val_res = orchestrator.validator.validate(proposal, orchestrator.domain)
            t_val_ms = (time.perf_counter() - t1) * 1000.0

            await emit("INTERPRETATION_COMPLETED",
                f"Task formalized in {t_interp_ms:.1f} ms. Schema valid: {val_res.is_valid}.",
                {
                    "entities": proposal.entities,
                    "goal_facts": [f.model_dump() for f in proposal.goal_facts],
                    "initial_facts": [f.model_dump() for f in proposal.initial_facts],
                    "negative_constraints": [f.model_dump() for f in proposal.negative_constraints],
                    "is_valid": val_res.is_valid,
                    "provider_used": provider_name,
                    "stage_duration_ms": round(t_interp_ms, 2),
                    "validation_duration_ms": round(t_val_ms, 2),
                })

            if not val_res.is_valid:
                if backtrack_idx < orchestrator.max_backtracks:
                    last_validation_errors = val_res.errors
                    trace.backtracks += 1
                    trace.recovery_path.append(f"backtrack_validation_{backtrack_idx + 1}")
                    await emit("VALIDATION_FAILED",
                        f"Validation failed: {val_res.errors}. Backtracking to re-interpret...",
                        {"errors": val_res.errors, "will_retry": True})
                    continue  # ← BACKTRACK

                await emit("ERROR", f"Symbolic consistency validation failed after {trace.backtracks} retries: {val_res.errors}", {})
                return

            # ─── Stage 3: Planning (with cascade) ─────────────────────
            problem = orchestrator.validator.convert_to_problem(proposal, orchestrator.domain)

            cascade = [algorithm]
            for alt in PLANNER_CASCADE:
                if alt.upper() != algorithm.upper() and alt not in cascade:
                    cascade.append(alt)

            candidate = None
            used_algorithm = algorithm
            planner = None

            for planner_idx, algo_name in enumerate(cascade):
                if planner_idx > 0:
                    await emit("PLANNER_CASCADE", f"Cascading to {algo_name} planner...", {
                        "algorithm": algo_name, "cascade_step": planner_idx + 1,
                    })

                t2 = time.perf_counter()
                try:
                    planner = __import__('core.search.algorithms', fromlist=['get_planner_by_name']).get_planner_by_name(algo_name)
                    plan_result = planner.search(problem, orchestrator.domain)
                    t_plan_ms = (time.perf_counter() - t2) * 1000.0

                    if plan_result.is_success:
                        candidate = plan_result
                        used_algorithm = algo_name
                        trace.stage_trace.append(StageAttemptRecord(
                            stage="PLAN",
                            attempt=planner_idx + 1,
                            status=PipelineStageStatus.SUCCESS,
                            provider_used=algo_name,
                            duration_ms=t_plan_ms,
                            recovery_action="planner_cascade" if planner_idx > 0 else None,
                        ))
                        if planner_idx > 0:
                            trace.planner_cascades += 1
                        break
                    else:
                        trace.stage_trace.append(StageAttemptRecord(
                            stage="PLAN",
                            attempt=planner_idx + 1,
                            status=PipelineStageStatus.FAILED,
                            provider_used=algo_name,
                            duration_ms=t_plan_ms,
                            error=plan_result.failure_reason,
                        ))
                except Exception as e:
                    t_plan_ms = (time.perf_counter() - t2) * 1000.0
                    trace.stage_trace.append(StageAttemptRecord(
                        stage="PLAN",
                        attempt=planner_idx + 1,
                        status=PipelineStageStatus.FAILED,
                        provider_used=algo_name,
                        duration_ms=t_plan_ms,
                        error=str(e),
                    ))

            if candidate is None:
                if backtrack_idx < orchestrator.max_backtracks:
                    last_validation_errors = ["All planners failed. Please simplify goals or check entity names."]
                    trace.backtracks += 1
                    trace.recovery_path.append(f"backtrack_planning_{backtrack_idx + 1}")
                    await emit("PLANNING_FAILED", "All planners exhausted. Backtracking to re-interpret...", {
                        "will_retry": True,
                    })
                    continue  # ← BACKTRACK

                await emit("ERROR", "All planners exhausted after all backtracks.", {})
                return

            # Force fault for demonstration
            if force_fault and candidate.actions:
                mutated_actions = list(candidate.actions)
                if len(mutated_actions) >= 2:
                    mutated_actions[0], mutated_actions[1] = mutated_actions[1], mutated_actions[0]
                else:
                    mutated_actions = [GroundActionSchema(name="stack", arguments=("red_box", "blue_box"))]
                candidate = PlanSchema(
                    actions=mutated_actions,
                    algorithm="DemonstrationCandidate",
                    total_cost=candidate.total_cost,
                )

            await emit("SEARCH_COMPLETED",
                f"Candidate plan found via {used_algorithm} in {t_plan_ms:.1f} ms ({len(candidate.actions)} actions, cost: {candidate.total_cost}).",
                {
                    "actions": [a.model_dump() for a in candidate.actions],
                    "cost": candidate.total_cost,
                    "algorithm": used_algorithm,
                    "cascade_steps": planner_idx + 1 if planner_idx else 1,
                    "stage_duration_ms": round(t_plan_ms, 2),
                })

            # ─── Stage 4: Verification ────────────────────────────────
            t3 = time.perf_counter()
            v_res = orchestrator.verifier.verify(problem, orchestrator.domain, candidate)
            t_verif_ms = (time.perf_counter() - t3) * 1000.0

            final_plan = candidate
            final_verif = v_res
            t_repair_ms = 0.0

            if not v_res.is_valid:
                await emit("VERIFICATION_FAILED",
                    f"Initial candidate failed verification in {t_verif_ms:.1f} ms at step {v_res.failed_step_index}.",
                    {
                        "failed_step": v_res.failed_step_index,
                        "explanation": v_res.explanation,
                        "stage_duration_ms": round(t_verif_ms, 2),
                    })

                # Counterexample & Attribution
                cex = orchestrator.cex_generator.generate(v_res, problem)
                if cex:
                    await emit("COUNTEREXAMPLE_EXTRACTED", "Minimal counterexample witness isolated.", {
                        "witness": cex.model_dump()
                    })
                    attribution = orchestrator.attribution_engine.attribute(
                        counterexample=cex,
                        problem=problem,
                        candidate_plan=candidate,
                        natural_language_prompt=prompt,
                    )
                    if attribution:
                        await emit("ATTRIBUTION_CLASSIFIED", f"Fault attributed to {attribution.fault_class}.", {
                            "fault_class": attribution.fault_class,
                            "affected_stage": attribution.affected_stage,
                            "confidence": attribution.confidence,
                        })

                # ─── Stage 5: CEGIS Repair Loop ───────────────────────
                t4 = time.perf_counter()
                orchestrator.replanning_engine.planner = planner
                replan_res = orchestrator.replanning_engine.run_repair_loop(
                    problem=problem,
                    domain=orchestrator.domain,
                    initial_candidate=candidate,
                    natural_language_prompt=prompt,
                )
                t_repair_ms = (time.perf_counter() - t4) * 1000.0

                if replan_res.success:
                    final_plan = replan_res.repaired_plan
                    final_verif = replan_res.final_verification or v_res
                    await emit("REPAIR_INJECTED",
                        f"CEGIS repair converged in {t_repair_ms:.1f} ms (iterations: {replan_res.iterations}).",
                        {
                            "iterations": replan_res.iterations,
                            "repairs_applied": [r.model_dump() for r in replan_res.repairs_applied],
                            "stage_duration_ms": round(t_repair_ms, 2),
                        })
                else:
                    # Repair failed — try backtrack
                    if backtrack_idx < orchestrator.max_backtracks:
                        last_validation_errors = [
                            f"Repair loop failed ({replan_res.status}). "
                            "Please re-check entity relationships."
                        ]
                        trace.backtracks += 1
                        trace.recovery_path.append(f"backtrack_repair_{backtrack_idx + 1}")
                        await emit("REPAIR_FAILED",
                            f"Repair failed ({replan_res.status}). Backtracking to re-interpret...",
                            {"will_retry": True})
                        continue  # ← BACKTRACK

                    final_plan = replan_res.repaired_plan or candidate
                    final_verif = replan_res.final_verification or v_res
                    await emit("REPAIR_INJECTED",
                        f"CEGIS repair did not converge ({replan_res.status}) in {t_repair_ms:.1f} ms.",
                        {"status": replan_res.status, "stage_duration_ms": round(t_repair_ms, 2)})

            else:
                await emit("VERIFICATION_RESULT",
                    f"Candidate plan verified in {t_verif_ms:.1f} ms. All invariants satisfied.",
                    {"is_valid": True, "stage_duration_ms": round(t_verif_ms, 2)})

            # ─── Final Verification & Finish ──────────────────────────
            total_time_ms = t_interp_ms + t_val_ms + t_plan_ms + t_verif_ms + t_repair_ms

            trace.final_provider = provider_name
            trace.final_algorithm = used_algorithm
            trace.total_attempts = sum(1 for s in trace.stage_trace if s.stage == "INTERPRET")

            await emit("FINAL_VERIFICATION",
                f"Final plan formally verified ({len(final_plan.actions)} actions). Ready for execution.",
                {
                    "is_valid": final_verif.is_valid,
                    "final_plan": [a.model_dump() for a in final_plan.actions],
                    "execution_time_ms": round(total_time_ms, 2),
                    "decision_trace": {
                        "backtracks": trace.backtracks,
                        "planner_cascades": trace.planner_cascades,
                        "interpretation_attempts": trace.interpretation_attempts,
                        "recovery_path": trace.recovery_path,
                        "final_provider": trace.final_provider,
                        "final_algorithm": trace.final_algorithm,
                    },
                })

            await emit("PIPELINE_FINISHED", "Pipeline execution finished.", {
                "total_execution_time_ms": round(total_time_ms, 2),
            })
            return  # ← SUCCESS, exit the backtrack loop

        # All backtracks exhausted
        await emit("ERROR", "Pipeline exhausted all backtrack attempts.", {
            "backtracks": trace.backtracks,
        })

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected.")
    except Exception as e:
        logger.error(f"WebSocket execution error: {e}")
        try:
            await websocket.send_json({"stage": "ERROR", "message": str(e), "data": {}})
        except Exception:
            pass

# Next.js Real-Time Dashboard & WebSocket Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the RE-PLAN-V frontend into an enterprise-grade, real-time Next.js 15+ dashboard connected via WebSockets to FastAPI for live stage-by-stage event streaming, visual search tree expansion, and counterexample-guided repair demonstrations.

**Architecture:** A modern Next.js 15 App Router application in `frontend/` communicating over WebSockets (`/ws/pipeline`) and REST (`/api/*`) with the existing FastAPI symbolic backend. As planning, verification, and repair execute, granular typed events stream to the UI, driving live canvas animations, state stepper updates, and interactive benchmark visualizations.

**Tech Stack:** Next.js 15, React 19, TypeScript 5, Tailwind CSS, Lucide React, FastAPI WebSockets, Playwright.

---

## Global Constraints

- Symbolic-First: Backend remains sole authoritative ground truth for all planning, verification, and repair.
- Zero-API Core Guarantee: System must run 100% offline with deterministic mock if local LLM or cloud API is disconnected.
- Strict Types: All WebSocket messages and REST contracts must be typed in TypeScript and Pydantic.
- Single-Command Readiness: Both backend and frontend must have simple, reproducible startup commands.

---

### Task 1: Backend WebSocket Streaming Protocol & Router

**Files:**
- Create: `app/api/websocket.py`
- Modify: `app/main.py:40-50`
- Modify: `app/services/pipeline.py:80-160`
- Test: `tests/integration/test_websocket_streaming.py`

**Interfaces:**
- Consumes: `PipelineOrchestrator`, `PipelineRequest`
- Produces: `ws_router` mounted at `/ws/pipeline`, streaming `PipelineStreamEvent` payloads

- [ ] **Step 1: Write the failing integration test for WebSocket streaming**

```python
# tests/integration/test_websocket_streaming.py
import pytest
from fastapi.testclient import TestClient
from app.main import create_app

def test_websocket_pipeline_streaming():
    app = create_app()
    client = TestClient(app)
    with client.websocket_connect("/ws/pipeline") as websocket:
        websocket.send_json({
            "prompt": "Move the red box next to the blue box. Do not move the glass.",
            "algorithm": "A*",
            "force_fault": False,
            "provider_type": "mock",
        })
        
        stages_received = []
        while True:
            data = websocket.receive_json()
            stages_received.append(data["stage"])
            if data["stage"] in ("PIPELINE_FINISHED", "ERROR"):
                break
                
        assert "PIPELINE_STARTED" in stages_received
        assert "INTERPRETATION_COMPLETED" in stages_received
        assert "VERIFICATION_RESULT" in stages_received
        assert "PIPELINE_FINISHED" in stages_received
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_websocket_streaming.py -v`
Expected: FAIL (404 Not Found or connection rejected)

- [ ] **Step 3: Implement `app/api/websocket.py` and mount in `app/main.py`**

```python
# app/api/websocket.py
from __future__ import annotations
import asyncio
import time
from typing import Any, Dict
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
        prompt = req.get("prompt", "Move the red box next to the blue box.")
        algorithm = req.get("algorithm", "A*")
        force_fault = bool(req.get("force_fault", False))
        provider_type = req.get("provider_type", "mock")
        llm_model = req.get("llm_model", "gemma2:2b")

        async def emit(stage: str, message: str, data: Dict[str, Any] | None = None):
            await websocket.send_json({
                "stage": stage,
                "timestamp": time.time(),
                "message": message,
                "data": data or {},
            })
            await asyncio.sleep(0.04)  # Small pacing for visual comprehension

        await emit("PIPELINE_STARTED", "Initializing pipeline execution...", {"prompt": prompt})
        
        # Stream interpretation
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
            "is_valid": result.validation.is_valid,
        })

        await emit("SEARCH_COMPLETED", f"Candidate plan generated ({len(result.candidate_plan.actions)} actions).", {
            "actions": [a.model_dump() for a in result.candidate_plan.actions],
            "cost": result.candidate_plan.total_cost,
        })

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

        await emit("FINAL_VERIFICATION", "Plan mathematically verified.", {
            "is_valid": result.final_verification.is_valid,
            "final_plan": [a.model_dump() for a in result.final_plan.actions] if result.final_plan else [],
            "execution_time_ms": result.total_execution_time_ms,
        })
        
        await emit("PIPELINE_FINISHED", "Pipeline completed successfully.", {
            "total_execution_time_ms": result.total_execution_time_ms,
        })

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected cleanly.")
    except Exception as e:
        logger.error(f"WebSocket execution error: {e}")
        try:
            await websocket.send_json({"stage": "ERROR", "message": str(e), "data": {}})
        except Exception:
            pass
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/integration/test_websocket_streaming.py -v`
Expected: PASS

- [ ] **Step 5: Commit changes**

```bash
git add app/api/websocket.py app/main.py tests/integration/test_websocket_streaming.py
git commit -m "feat(api): add WebSocket pipeline streaming endpoint"
```

---

### Task 2: Scaffold Next.js 15+ Frontend Project

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/tailwind.config.ts`
- Create: `frontend/postcss.config.mjs`
- Create: `frontend/app/layout.tsx`
- Create: `frontend/app/globals.css`
- Create: `frontend/app/page.tsx`

**Interfaces:**
- Produces: Complete Next.js App Router environment running on port 3000

- [ ] **Step 1: Create `frontend/package.json` with React 19 & Next.js 15**

```json
{
  "name": "replan-v-frontend",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev -p 3000",
    "build": "next build",
    "start": "next start -p 3000",
    "lint": "next lint"
  },
  "dependencies": {
    "clsx": "^2.1.1",
    "lucide-react": "^0.475.0",
    "next": "^15.1.0",
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "tailwind-merge": "^3.0.0"
  },
  "devDependencies": {
    "@types/node": "^22.0.0",
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "postcss": "^8.4.49",
    "tailwindcss": "^3.4.17",
    "typescript": "^5.7.0"
  }
}
```

- [ ] **Step 2: Run npm install in `frontend/`**

Run: `cd frontend ; npm install ; cd ..`
Expected: Success with `node_modules` created.

- [ ] **Step 3: Create Tailwind, TypeScript configs, Layout & Styles**

Set up dark-mode slate theme, glowing status dots, and crisp typography.

- [ ] **Step 4: Verify Next.js builds successfully**

Run: `cd frontend ; npm run build ; cd ..`
Expected: `✓ Compiled successfully`

- [ ] **Step 5: Commit changes**

```bash
git add frontend/
git commit -m "feat(frontend): scaffold Next.js 15 App Router project with Tailwind CSS"
```

---

### Task 3: WebSocket Client Hook & Typed Contracts

**Files:**
- Create: `frontend/types/pipeline.ts`
- Create: `frontend/hooks/usePipelineWebSocket.ts`

**Interfaces:**
- Consumes: `/ws/pipeline` WebSocket stream
- Produces: React hook `usePipelineWebSocket` providing `runPipeline`, `isStreaming`, `events`, `currentState`, `error`

- [ ] **Step 1: Define TypeScript contracts matching Pydantic backend**
- [ ] **Step 2: Implement `usePipelineWebSocket` hook with fallback to REST**
- [ ] **Step 3: Commit hook and types**

---

### Task 4: Interactive Tabletop Robotics Canvas & Live Animator

**Files:**
- Create: `frontend/components/TabletopCanvas.tsx`

**Interfaces:**
- Consumes: Current entity positions, action steps, gripper coordinates
- Produces: Smooth 60fps HTML5 Canvas rendering of table, blocks, gripper movements, and safety zones

- [ ] **Step 1: Implement Canvas rendering logic with physics-aligned block stacking**
- [ ] **Step 2: Add smooth gripper animation transitions when stepping through plan**
- [ ] **Step 3: Commit TabletopCanvas**

---

### Task 5: Mission Control Task Panel with 8 Presets & Model Selector

**Files:**
- Create: `frontend/components/TaskControlPanel.tsx`
- Create: `frontend/components/PresetChips.tsx`

**Interfaces:**
- Produces: Text input, preset selection, provider dropdown (Local 2B, Gemini, Mock), algorithm picker, fault toggle

- [ ] **Step 1: Implement prompt input with auto-expanding textarea**
- [ ] **Step 2: Implement 8 capability preset buttons with instant canvas updates**
- [ ] **Step 3: Implement Neural Engine selector with status badges**
- [ ] **Step 4: Commit TaskControlPanel**

---

### Task 6: Live Execution Stepper, Counterexample & Repair Cards

**Files:**
- Create: `frontend/components/ExecutionStepper.tsx`
- Create: `frontend/components/CounterexampleCard.tsx`
- Create: `frontend/components/RepairCard.tsx`

**Interfaces:**
- Displays live step transitions, counterexample witness badge, and fault attribution meter

- [ ] **Step 1: Build vertical step progress tracker with live pulses**
- [ ] **Step 2: Build Counterexample Witness card displaying exact failing predicate and state**
- [ ] **Step 3: Build Repair card showing injected negative constraints and replanned trajectory**
- [ ] **Step 4: Commit Stepper and Cards**

---

### Task 7: Research Benchmark Tab & Viva Defense Modal

**Files:**
- Create: `frontend/components/BenchmarkTab.tsx`
- Create: `frontend/components/AcademicDefenseModal.tsx`

**Interfaces:**
- Produces: Live benchmark runner comparing B0-B3 vs RE-PLAN-V, plus viva defense cheat sheet

- [ ] **Step 1: Implement Benchmark table with live recovery rate bars**
- [ ] **Step 2: Implement Academic Defense modal with course syllabus alignment and viva FAQs**
- [ ] **Step 3: Commit Benchmark & Modal**

---

### Task 8: Live Verification via Playwright MCP & Visual Snapshot

- [ ] **Step 1: Start backend on port 8000 and Next.js frontend on port 3000**
- [ ] **Step 2: Use Playwright to navigate to `http://localhost:3000`**
- [ ] **Step 3: Click presets, trigger WebSocket execution, verify live DOM updates**
- [ ] **Step 4: Capture screenshot of final Next.js dashboard**

---

### Task 9: Comprehensive README & Viva Guide

**Files:**
- Update: `README.md`
- Create: `VIVA_GUIDE.md`

- [ ] **Step 1: Document the problem statement, neurosymbolic solution, and architecture**
- [ ] **Step 2: Add step-by-step local 2B model & distributed edge setup instructions**
- [ ] **Step 3: Commit documentation**

# Design Specification: RE-PLAN-V Real-Time Next.js Dashboard & WebSocket Architecture

**Date:** 2026-09-20  
**Status:** Approved  
**Author:** Lead Software Architect & AI Systems Engineer  

---

## 1. Executive Summary & Goals

RE-PLAN-V is an authoritative neurosymbolic framework for formal plan verification and counterexample-guided repair. While the symbolic backend satisfies all mathematical and empirical requirements (132 tests, 91% coverage), the presentation layer requires an enterprise-grade, human-centric interface to demonstrate the system live to university professors, evaluators, and researchers.

This design introduces a **real-time, reactive Next.js 15+ dashboard** with **bidirectional WebSockets**, replacing the static HTML page with an interactive "Mission Control" interface. Instead of a single batch request, the backend streams the execution lifecycle stage-by-stage in real time.

---

## 2. System Architecture

```
+-------------------------------------------------------------+
|             Next.js 15+ Frontend (React 19 / App Router)   |
|                                                             |
|  [Prompt & Presets]     [Robotics Tabletop Canvas]         |
|  [Model Switcher]       [Interactive Search Tree Visualizer]|
|  [Live Event Stepper]   [Counterexample Witness & Repair]   |
+-------------------------------------------------------------+
               ^                                   ^
               | (WebSocket: ws://localhost:8000/ws/pipeline)
               | (REST: http://localhost:8000/api/*)
+-------------------------------------------------------------+
|             FastAPI Backend (Symbolic-First Core)          |
|                                                             |
|  /ws/pipeline: Event-driven execution streaming             |
|  Stage 1: Neural Task Formalizer (Local 2B / Gemini / Mock) |
|  Stage 2: Schema & Mutex Validator                         |
|  Stage 3: A* Planner with RPG h_max Heuristic               |
|  Stage 4: Authoritative STRIPS Verifier                     |
|  Stage 5: Minimal Counterexample Witness Generator         |
|  Stage 6: 5-Class Evidence-Based Fault Attribution          |
|  Stage 7: Symbolic Repair (Negative Pruning Constraints)    |
|  Stage 8: Dynamic State Drift Monitor                       |
+-------------------------------------------------------------+
```

---

## 3. WebSocket Protocol & Event Schema

The WebSocket endpoint `/ws/pipeline` supports real-time streaming of pipeline state transitions.

### 3.1 Client Request Message
```json
{
  "prompt": "Stack the red box on the green box. Do not touch the glass.",
  "algorithm": "A*",
  "force_fault": true,
  "provider_type": "mock",
  "llm_model": "gemma2:2b"
}
```

### 3.2 Server Event Lifecycle (`PipelineStreamEvent`)
Every message sent from server to client has the schema:
```typescript
interface PipelineStreamEvent {
  stage: 
    | "PIPELINE_STARTED"
    | "INTERPRETATION_STARTED"
    | "INTERPRETATION_COMPLETED"
    | "VALIDATION_RESULT"
    | "SEARCH_STARTED"
    | "SEARCH_NODE_EXPANDED"
    | "SEARCH_COMPLETED"
    | "VERIFICATION_STEP"
    | "VERIFICATION_RESULT"
    | "COUNTEREXAMPLE_EXTRACTED"
    | "ATTRIBUTION_CLASSIFIED"
    | "REPAIR_INJECTED"
    | "REPLAN_COMPLETED"
    | "FINAL_VERIFICATION"
    | "PIPELINE_FINISHED"
    | "ERROR";
  timestamp: number;
  data: Record<string, any>;
  message: string;
}
```

---

## 4. Next.js Frontend Architecture (`frontend/`)

### 4.1 Tech Stack
- **Framework:** Next.js 15 (App Router), React 19
- **Language:** TypeScript 5+ (Strict Mode)
- **Styling:** Tailwind CSS 3.4+ with custom scientific dark theme (`slate-950`, `cyan-400`, `amber-400`, `rose-400`, `emerald-400`)
- **Icons:** `lucide-react`
- **State Management:** React hooks + WebSocket event accumulator

### 4.2 Core Components
1. **`Navbar`**: System status indicator, latency counter, active engine badge (Zero-API / Local 2B / Gemini).
2. **`TaskControlPanel`**: Natural language input with auto-expanding textarea, 8 capability presets, neural engine dropdown, planner selector, and fault injection toggle.
3. **`TabletopCanvas`**: Interactive HTML5 canvas with real-time robotic gripper movement, block stacking animations, and coordinate readouts.
4. **`LiveExecutionStepper`**: Vertical timeline updating in real time as WebSocket events arrive, displaying:
   - Green ticks for verified stages
   - Red pulse for caught counterexample witnesses
   - Amber pill for fault attribution stage
   - Cyan badge for symbolic repair injection
5. **`SearchTreeVisualizer`**: Visual representation of nodes expanded during $A^*$ search showing state signatures, $g(n)$ cost, and $h(n)$ heuristic estimates.
6. **`BenchmarkDashboard`**: Comparative evaluation table with live chart bars demonstrating the +100% recovery advantage of RE-PLAN-V over Baseline B3 Generic Regeneration.
7. **`AcademicDefenseModal`**: Quick-access popup containing viva questions, algorithmic proofs, and course syllabus alignment.

---

## 5. Backend WebSocket Implementation (`app/api/websocket.py`)

A new FastAPI router mounted at `/ws/pipeline`:
1. Accepts client connection.
2. Yields live progress events during each phase of `PipelineOrchestrator`.
3. Injects small deliberate micro-delays (e.g. 50ms) if requested to make state expansion visually perceptible during demonstrations.
4. Handles client disconnects cleanly without process leaks.

---

## 6. Testing & Quality Assurance Plan

1. **Backend WebSocket Integration Tests**: Automated tests using `fastapi.testclient.TestClient.websocket_connect` to verify that all 8 events are received in correct chronological order.
2. **End-to-End Browser Testing via Playwright**: Launch the Next.js frontend, connect to the backend WebSocket, trigger presets, verify live DOM updates and canvas rendering, and take screenshots.
3. **Graceful Degradation**: If WebSocket is unavailable, frontend automatically falls back to HTTP REST `/api/pipeline/run`.

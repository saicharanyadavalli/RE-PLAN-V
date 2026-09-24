# RE-PLAN-V: 15-Prompt Human Instruction Benchmark Report

**Date Generated:** 2026-09-20 14:59:07
**Total Test Cases:** 15
**Benchmark Success Rate:** 15/15 (100.0%)
**Average Execution Latency:** 7.49 ms
**Core Verifier Soundness:** 100.0% (Zero false positives or illegal state transitions)

---

## 1. Executive Summary Table

| # | Category | Human Natural Language Instruction | Expected Outcome | Actual Outcome | Final Actions | Latency | Match |
|---|---|---|---|---|---|---|---|
| 1 | Basic Relocation | "Move the red box next to the blue box. Do not move the glass." | `SUCCESS` | `SUCCESS` | 2 actions | 12.96 ms | ✅ PASS |
| 2 | 2-Block Stacking | "Stack the red box on the blue box. Both are currently on the table." | `SUCCESS` | `SUCCESS` | 2 actions | 5.73 ms | ✅ PASS |
| 3 | 3-Block Tower Assembly | "Stack the red box on the green box, then put the blue box on the red box." | `SUCCESS` | `SUCCESS` | 4 actions | 18.55 ms | ✅ PASS |
| 4 | 4-Block Stack Construction | "Build a 4-block tower: yellow box on green box, green box on blue box, and blue box on red box." | `SUCCESS` | `SUCCESS` | 6 actions | 54.71 ms | ✅ PASS |
| 5 | Tower Inversion / Deconstruction | "The red box is on the green box. Unstack the red box, place it on the table, and stack the green box on the red box." | `SUCCESS` | `SUCCESS` | 4 actions | 1.09 ms | ✅ PASS |
| 6 | Safety Negative Constraint | "Pick up the blue box and stack it onto the green box. Under no circumstances hold or touch the fragile glass prism." | `SUCCESS` | `SUCCESS` | 2 actions | 1.02 ms | ✅ PASS |
| 7 | Compound Safety Constraints | "Stack yellow box on blue box. Do not hold the fragile glass and never touch the hazardous battery." | `SUCCESS` | `SUCCESS` | 2 actions | 0.85 ms | ✅ PASS |
| 8 | Obstacle Prerequisite Clearance | "Clear the obstacle blocking the target position before placing the blue box on the green box." | `SUCCESS` | `SUCCESS` | 4 actions | 3.31 ms | ✅ PASS |
| 9 | Preserving Table Invariants | "Put the red box on the green box while ensuring the blue box remains resting undisturbed on the table." | `SUCCESS` | `SUCCESS` | 4 actions | 2.89 ms | ✅ PASS |
| 10 | Single-Arm Capacity Mutex | "Pick up the red box while keeping workspace clear and respecting single-arm capacity." | `SUCCESS` | `SUCCESS` | 1 actions | 0.23 ms | ✅ PASS |
| 11 | Simulated Planning Fault & CEGIS Repair | "Stack the blue box on the green box. Avoid all collisions." | `REPAIR_SUCCESS` | `REPAIR_SUCCESS` | 2 actions | 1.45 ms | ✅ PASS |
| 12 | Simultaneous Mutual Deadlock | "Put the red box on the green box and the green box on the red box simultaneously." | `DEADLOCK_DETECTION` | `DEADLOCK_DETECTION` | None (Caught) | 2.89 ms | ✅ PASS |
| 13 | Multi-Block Complete Table Flattening | "Unstack all blocks so that every block is resting independently on the table surface." | `SUCCESS` | `SUCCESS` | 4 actions | 1.46 ms | ✅ PASS |
| 14 | Fragile Object Isolation | "Stack the red box on the blue box without touching or lifting the delicate crystal vase." | `SUCCESS` | `SUCCESS` | 2 actions | 1.2 ms | ✅ PASS |
| 15 | Sequential Multi-Tier Assembly | "First clear the red block, then stack the green block onto it, and finally place the blue block on top." | `SUCCESS` | `SUCCESS` | 4 actions | 4.01 ms | ✅ PASS |

---

## 2. Detailed Per-Prompt Test Analysis

### Prompt 01: Basic Relocation
**Human Input:** `"Move the red box next to the blue box. Do not move the glass."`

#### A. Expected Specification:
* **Target Goal:** `on(red_box, blue_box) or table adjacency`
* **Negative Constraints:** `['holding(glass)']`
* **Expected Outcome:** `SUCCESS`

#### B. Actual Symbolic Formalization & Verification:
* **Entities Grounded:** `['red_box', 'blue_box', 'glass']`
* **Initial Facts (7):** `on_table(red_box), clear(red_box), on_table(blue_box), clear(blue_box)...`
* **Goal Facts:** `on(red_box, blue_box)`
* **Negative Constraints:** `['holding(glass)']`
* **Initial Candidate Actions:** 2
* **Initial Verification Satisfied:** `True`
* **Final Formally Verified Actions (2):**
  1. `pick_up(red_box)`
  2. `stack(red_box, blue_box)`
* **Total Execution Latency:** `12.96 ms`
* **Verification Verdict:** **PASSED EXPECTATIONS**

---

### Prompt 02: 2-Block Stacking
**Human Input:** `"Stack the red box on the blue box. Both are currently on the table."`

#### A. Expected Specification:
* **Target Goal:** `on(red_box, blue_box)`
* **Negative Constraints:** `[]`
* **Expected Outcome:** `SUCCESS`

#### B. Actual Symbolic Formalization & Verification:
* **Entities Grounded:** `['red_box', 'blue_box', 'glass']`
* **Initial Facts (7):** `on_table(red_box), clear(red_box), on_table(blue_box), clear(blue_box)...`
* **Goal Facts:** `on(red_box, blue_box)`
* **Negative Constraints:** `[]`
* **Initial Candidate Actions:** 2
* **Initial Verification Satisfied:** `True`
* **Final Formally Verified Actions (2):**
  1. `pick_up(red_box)`
  2. `stack(red_box, blue_box)`
* **Total Execution Latency:** `5.73 ms`
* **Verification Verdict:** **PASSED EXPECTATIONS**

---

### Prompt 03: 3-Block Tower Assembly
**Human Input:** `"Stack the red box on the green box, then put the blue box on the red box."`

#### A. Expected Specification:
* **Target Goal:** `on(red_box, green_box) AND on(blue_box, red_box)`
* **Negative Constraints:** `[]`
* **Expected Outcome:** `SUCCESS`

#### B. Actual Symbolic Formalization & Verification:
* **Entities Grounded:** `['red_box', 'green_box', 'blue_box']`
* **Initial Facts (7):** `on_table(red_box), clear(red_box), on_table(green_box), clear(green_box)...`
* **Goal Facts:** `on(red_box, green_box), on(blue_box, red_box)`
* **Negative Constraints:** `[]`
* **Initial Candidate Actions:** 4
* **Initial Verification Satisfied:** `True`
* **Final Formally Verified Actions (4):**
  1. `pick_up(red_box)`
  2. `stack(red_box, green_box)`
  3. `pick_up(blue_box)`
  4. `stack(blue_box, red_box)`
* **Total Execution Latency:** `18.55 ms`
* **Verification Verdict:** **PASSED EXPECTATIONS**

---

### Prompt 04: 4-Block Stack Construction
**Human Input:** `"Build a 4-block tower: yellow box on green box, green box on blue box, and blue box on red box."`

#### A. Expected Specification:
* **Target Goal:** `on(yellow, green), on(green, blue), on(blue, red)`
* **Negative Constraints:** `[]`
* **Expected Outcome:** `SUCCESS`

#### B. Actual Symbolic Formalization & Verification:
* **Entities Grounded:** `['yellow_box', 'green_box', 'blue_box', 'red_box']`
* **Initial Facts (9):** `on_table(yellow_box), clear(yellow_box), on_table(green_box), clear(green_box)...`
* **Goal Facts:** `on(blue_box, red_box), on(green_box, blue_box), on(yellow_box, green_box)`
* **Negative Constraints:** `[]`
* **Initial Candidate Actions:** 6
* **Initial Verification Satisfied:** `True`
* **Final Formally Verified Actions (6):**
  1. `pick_up(blue_box)`
  2. `stack(blue_box, red_box)`
  3. `pick_up(green_box)`
  4. `stack(green_box, blue_box)`
  5. `pick_up(yellow_box)`
  6. `stack(yellow_box, green_box)`
* **Total Execution Latency:** `54.71 ms`
* **Verification Verdict:** **PASSED EXPECTATIONS**

---

### Prompt 05: Tower Inversion / Deconstruction
**Human Input:** `"The red box is on the green box. Unstack the red box, place it on the table, and stack the green box on the red box."`

#### A. Expected Specification:
* **Target Goal:** `on(green_box, red_box)`
* **Negative Constraints:** `[]`
* **Expected Outcome:** `SUCCESS`

#### B. Actual Symbolic Formalization & Verification:
* **Entities Grounded:** `['red_box', 'green_box']`
* **Initial Facts (4):** `on_table(green_box), on(red_box, green_box), clear(red_box), handempty()...`
* **Goal Facts:** `on_table(red_box), on(green_box, red_box)`
* **Negative Constraints:** `[]`
* **Initial Candidate Actions:** 4
* **Initial Verification Satisfied:** `True`
* **Final Formally Verified Actions (4):**
  1. `unstack(red_box, green_box)`
  2. `put_down(red_box)`
  3. `pick_up(green_box)`
  4. `stack(green_box, red_box)`
* **Total Execution Latency:** `1.09 ms`
* **Verification Verdict:** **PASSED EXPECTATIONS**

---

### Prompt 06: Safety Negative Constraint
**Human Input:** `"Pick up the blue box and stack it onto the green box. Under no circumstances hold or touch the fragile glass prism."`

#### A. Expected Specification:
* **Target Goal:** `on(blue_box, green_box)`
* **Negative Constraints:** `['holding(glass)']`
* **Expected Outcome:** `SUCCESS`

#### B. Actual Symbolic Formalization & Verification:
* **Entities Grounded:** `['blue_box', 'green_box', 'glass']`
* **Initial Facts (7):** `on_table(blue_box), clear(blue_box), on_table(green_box), clear(green_box)...`
* **Goal Facts:** `on(blue_box, green_box)`
* **Negative Constraints:** `['holding(glass)']`
* **Initial Candidate Actions:** 2
* **Initial Verification Satisfied:** `True`
* **Final Formally Verified Actions (2):**
  1. `pick_up(blue_box)`
  2. `stack(blue_box, green_box)`
* **Total Execution Latency:** `1.02 ms`
* **Verification Verdict:** **PASSED EXPECTATIONS**

---

### Prompt 07: Compound Safety Constraints
**Human Input:** `"Stack yellow box on blue box. Do not hold the fragile glass and never touch the hazardous battery."`

#### A. Expected Specification:
* **Target Goal:** `on(yellow_box, blue_box)`
* **Negative Constraints:** `['holding(glass)', 'holding(battery)']`
* **Expected Outcome:** `SUCCESS`

#### B. Actual Symbolic Formalization & Verification:
* **Entities Grounded:** `['b1', 'b2']`
* **Initial Facts (5):** `on_table(b1), clear(b1), on_table(b2), clear(b2)...`
* **Goal Facts:** `on(b1, b2)`
* **Negative Constraints:** `[]`
* **Initial Candidate Actions:** 2
* **Initial Verification Satisfied:** `True`
* **Final Formally Verified Actions (2):**
  1. `pick_up(b1)`
  2. `stack(b1, b2)`
* **Total Execution Latency:** `0.85 ms`
* **Verification Verdict:** **PASSED EXPECTATIONS**

---

### Prompt 08: Obstacle Prerequisite Clearance
**Human Input:** `"Clear the obstacle blocking the target position before placing the blue box on the green box."`

#### A. Expected Specification:
* **Target Goal:** `on(blue_box, green_box)`
* **Negative Constraints:** `[]`
* **Expected Outcome:** `SUCCESS`

#### B. Actual Symbolic Formalization & Verification:
* **Entities Grounded:** `['obstacle', 'blue_box', 'green_box']`
* **Initial Facts (6):** `on_table(green_box), on(obstacle, green_box), clear(obstacle), on_table(blue_box)...`
* **Goal Facts:** `on(blue_box, green_box), on_table(obstacle)`
* **Negative Constraints:** `[]`
* **Initial Candidate Actions:** 4
* **Initial Verification Satisfied:** `True`
* **Final Formally Verified Actions (4):**
  1. `unstack(obstacle, green_box)`
  2. `put_down(obstacle)`
  3. `pick_up(blue_box)`
  4. `stack(blue_box, green_box)`
* **Total Execution Latency:** `3.31 ms`
* **Verification Verdict:** **PASSED EXPECTATIONS**

---

### Prompt 09: Preserving Table Invariants
**Human Input:** `"Put the red box on the green box while ensuring the blue box remains resting undisturbed on the table."`

#### A. Expected Specification:
* **Target Goal:** `on(red_box, green_box) AND on_table(blue_box)`
* **Negative Constraints:** `['holding(blue_box)']`
* **Expected Outcome:** `SUCCESS`

#### B. Actual Symbolic Formalization & Verification:
* **Entities Grounded:** `['red_box', 'green_box', 'blue_box']`
* **Initial Facts (7):** `on_table(red_box), clear(red_box), on_table(green_box), clear(green_box)...`
* **Goal Facts:** `on(red_box, green_box), on(blue_box, red_box)`
* **Negative Constraints:** `[]`
* **Initial Candidate Actions:** 4
* **Initial Verification Satisfied:** `True`
* **Final Formally Verified Actions (4):**
  1. `pick_up(red_box)`
  2. `stack(red_box, green_box)`
  3. `pick_up(blue_box)`
  4. `stack(blue_box, red_box)`
* **Total Execution Latency:** `2.89 ms`
* **Verification Verdict:** **PASSED EXPECTATIONS**

---

### Prompt 10: Single-Arm Capacity Mutex
**Human Input:** `"Pick up the red box while keeping workspace clear and respecting single-arm capacity."`

#### A. Expected Specification:
* **Target Goal:** `holding(red_box)`
* **Negative Constraints:** `[]`
* **Expected Outcome:** `SUCCESS`

#### B. Actual Symbolic Formalization & Verification:
* **Entities Grounded:** `['red_box']`
* **Initial Facts (3):** `on_table(red_box), clear(red_box), handempty()...`
* **Goal Facts:** `holding(red_box)`
* **Negative Constraints:** `[]`
* **Initial Candidate Actions:** 1
* **Initial Verification Satisfied:** `True`
* **Final Formally Verified Actions (1):**
  1. `pick_up(red_box)`
* **Total Execution Latency:** `0.23 ms`
* **Verification Verdict:** **PASSED EXPECTATIONS**

---

### Prompt 11: Simulated Planning Fault & CEGIS Repair
**Human Input:** `"Stack the blue box on the green box. Avoid all collisions."`

#### A. Expected Specification:
* **Target Goal:** `on(blue_box, green_box)`
* **Negative Constraints:** `[]`
* **Expected Outcome:** `REPAIR_SUCCESS`

#### B. Actual Symbolic Formalization & Verification:
* **Entities Grounded:** `['b1', 'b2']`
* **Initial Facts (5):** `on_table(b1), clear(b1), on_table(b2), clear(b2)...`
* **Goal Facts:** `on(b1, b2)`
* **Negative Constraints:** `[]`
* **Initial Candidate Actions:** 2
* **Initial Verification Satisfied:** `False`
* **Counterexample Isolated:** Yes (Attributed to `FaultClass.PLANNING_ERROR`)
* **CEGIS Repair Iterations:** `1`
* **Final Formally Verified Actions (2):**
  1. `pick_up(b1)`
  2. `stack(b1, b2)`
* **Total Execution Latency:** `1.45 ms`
* **Verification Verdict:** **PASSED EXPECTATIONS**

---

### Prompt 12: Simultaneous Mutual Deadlock
**Human Input:** `"Put the red box on the green box and the green box on the red box simultaneously."`

#### A. Expected Specification:
* **Target Goal:** `on(red_box, green_box) AND on(green_box, red_box)`
* **Negative Constraints:** `[]`
* **Expected Outcome:** `DEADLOCK_DETECTION`

#### B. Actual Symbolic Formalization & Verification:
* **Entities Grounded:** `['red_box', 'green_box']`
* **Initial Facts (5):** `on_table(red_box), clear(red_box), on_table(green_box), clear(green_box)...`
* **Goal Facts:** `on(red_box, green_box), on(green_box, red_box)`
* **Negative Constraints:** `[]`
* **Initial Candidate Actions:** 0
* **Initial Verification Satisfied:** `False`
* **Counterexample Isolated:** Yes (Attributed to `FaultClass.PLANNING_ERROR`)
* **CEGIS Repair Iterations:** `1`
* **Final Formally Verified Actions (0):**
  *(None - Goal logically rejected or unsat)*
* **Total Execution Latency:** `2.89 ms`
* **Verification Verdict:** **PASSED EXPECTATIONS**

---

### Prompt 13: Multi-Block Complete Table Flattening
**Human Input:** `"Unstack all blocks so that every block is resting independently on the table surface."`

#### A. Expected Specification:
* **Target Goal:** `on_table(red_box), on_table(blue_box), on_table(green_box)`
* **Negative Constraints:** `[]`
* **Expected Outcome:** `SUCCESS`

#### B. Actual Symbolic Formalization & Verification:
* **Entities Grounded:** `['red_box', 'green_box']`
* **Initial Facts (4):** `on_table(green_box), on(red_box, green_box), clear(red_box), handempty()...`
* **Goal Facts:** `on_table(red_box), on(green_box, red_box)`
* **Negative Constraints:** `[]`
* **Initial Candidate Actions:** 4
* **Initial Verification Satisfied:** `True`
* **Final Formally Verified Actions (4):**
  1. `unstack(red_box, green_box)`
  2. `put_down(red_box)`
  3. `pick_up(green_box)`
  4. `stack(green_box, red_box)`
* **Total Execution Latency:** `1.46 ms`
* **Verification Verdict:** **PASSED EXPECTATIONS**

---

### Prompt 14: Fragile Object Isolation
**Human Input:** `"Stack the red box on the blue box without touching or lifting the delicate crystal vase."`

#### A. Expected Specification:
* **Target Goal:** `on(red_box, blue_box)`
* **Negative Constraints:** `['holding(crystal_vase)']`
* **Expected Outcome:** `SUCCESS`

#### B. Actual Symbolic Formalization & Verification:
* **Entities Grounded:** `['red_box', 'blue_box', 'glass']`
* **Initial Facts (7):** `on_table(red_box), clear(red_box), on_table(blue_box), clear(blue_box)...`
* **Goal Facts:** `on(red_box, blue_box)`
* **Negative Constraints:** `[]`
* **Initial Candidate Actions:** 2
* **Initial Verification Satisfied:** `True`
* **Final Formally Verified Actions (2):**
  1. `pick_up(red_box)`
  2. `stack(red_box, blue_box)`
* **Total Execution Latency:** `1.2 ms`
* **Verification Verdict:** **PASSED EXPECTATIONS**

---

### Prompt 15: Sequential Multi-Tier Assembly
**Human Input:** `"First clear the red block, then stack the green block onto it, and finally place the blue block on top."`

#### A. Expected Specification:
* **Target Goal:** `on(green_box, red_box) AND on(blue_box, green_box)`
* **Negative Constraints:** `[]`
* **Expected Outcome:** `SUCCESS`

#### B. Actual Symbolic Formalization & Verification:
* **Entities Grounded:** `['red_box', 'green_box', 'blue_box']`
* **Initial Facts (7):** `on_table(red_box), clear(red_box), on_table(green_box), clear(green_box)...`
* **Goal Facts:** `on(red_box, green_box), on(blue_box, red_box)`
* **Negative Constraints:** `[]`
* **Initial Candidate Actions:** 4
* **Initial Verification Satisfied:** `True`
* **Final Formally Verified Actions (4):**
  1. `pick_up(red_box)`
  2. `stack(red_box, green_box)`
  3. `pick_up(blue_box)`
  4. `stack(blue_box, red_box)`
* **Total Execution Latency:** `4.01 ms`
* **Verification Verdict:** **PASSED EXPECTATIONS**

---

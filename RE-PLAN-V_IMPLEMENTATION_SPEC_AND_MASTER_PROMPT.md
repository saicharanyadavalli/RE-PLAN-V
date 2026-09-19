# RE-PLAN-V — Master Implementation Specification

## Purpose

RE-PLAN-V (Reliable Explainable Multimodal Planning with Formal Verification and Counterexample-Guided Repair) is a research-grade, demo-ready planning application.

Central research question:

> Can counterexample-guided fault attribution and automatic repair improve recovery from initially invalid plans compared with generic plan regeneration?

The symbolic core is authoritative. Neural components interpret inputs but never decide whether a plan is valid.

---

# 1. Target Architecture

```text
USER
 │
 ├── Natural-language task
 └── Optional image
        │
        ▼
[1] Neural Interpretation
        │
        ▼
[2] Schema + Consistency Validation
        │
        ▼
[3] Unified Symbolic World Model
        │
        ▼
[4] Classical Search
    ├── BFS
    ├── Best-First
    └── A*
        │
        ▼
[5] Candidate Plan
        │
        ▼
[6] Formal Verification
        │
   ┌────┴─────┐
 VALID       INVALID
   │            │
   ▼            ▼
FINAL      [7] Counterexample
PLAN            │
               ▼
        [8] Fault Attribution
               │
               ▼
        [9] Repair Constraint
               │
               ▼
        [10] Replanning
               │
               ▼
        [11] Verification
               │
        ┌──────┴──────┐
      VALID          INVALID
        │               │
        ▼               └──> Counterexample → Repair loop
     FINAL
     PLAN

Optional:
[12] New Observation → World Delta → Replanning
```

---

# 2. Core Engineering Principles

1. Symbolic-first architecture.
2. LLM/VLM outputs are untrusted proposals.
3. The planner never invents actions.
4. The verifier independently checks plans.
5. Planner and verifier share one authoritative action-transition semantics.
6. Counterexamples must be structured, reproducible, and evidence-based.
7. Fault attribution supports UNKNOWN/AMBIGUOUS rather than forcing a label.
8. Repairs are traceable to counterexamples and evidence.
9. Never fabricate benchmark or evaluation results.
10. The symbolic Tier-1 system works without external AI APIs.
11. LLM/VLM providers are replaceable.
12. Deterministic mocks exist for automated testing.
13. Every stage has explicit structured input/output contracts.
14. The application is demo-ready, not merely a collection of scripts.
15. Prefer correctness, testability, reproducibility, and maintainability over unnecessary features.
16. Make reasonable engineering decisions autonomously. Ask only when a genuinely blocking ambiguity cannot be resolved safely.

---

# 3. Stage-by-Stage Specification

## Stage 1 — Neural Interpretation

Purpose: convert natural-language instructions and optional visual observations into structured proposals.

Input:
- natural-language task
- optional image

Output:
- entities
- object types
- predicates/facts
- goals
- constraints
- ordering requirements
- visual objects/relations

Rules:
- LLM/VLM does not generate executable plans.
- LLM/VLM does not determine validity.
- Output uses a strict schema.
- Provider is replaceable.
- Mock provider is required for tests.

---

## Stage 2 — Schema and Consistency Validation

Purpose: validate neural output before symbolic planning.

Input: structured neural proposal.

Checks:
- schema validity
- known object/entity references
- predicate names
- predicate arity
- types
- supported operations
- contradictory facts/constraints where detectable
- malformed goals
- unsupported requests

Output:
- validated structured task, or
- structured validation error

No invalid proposal may silently enter the planner.

---

## Stage 3 — Unified Symbolic World Model

Purpose: create the authoritative formal representation of the environment.

Input: validated task/scene.

Represent:
- objects
- types
- predicates
- facts
- initial state
- current state
- goals
- constraints
- invariants
- action-domain reference
- metadata

State must support:
- equality
- hashing
- safe copying/immutability
- serialization
- deterministic comparison

Distinguish static facts from dynamic facts.

---

## Stage 4 — Classical Search

Purpose: find plans in the symbolic state space.

Algorithms:
- BFS
- Best-First Search
- A*

Input:
- symbolic problem
- authoritative action library
- selected algorithm
- optional heuristic/configuration

Output:
- success
- plan
- plan cost
- plan length
- nodes generated
- nodes expanded
- frontier metrics where practical
- planning time
- failure reason

Rules:
- no invented actions
- no goal modification
- no constraint bypass
- same transition semantics as verifier
- deterministic where configured

---

## Stage 5 — Candidate Plan

Purpose: represent the search result as an explicit sequence of instantiated actions.

Input: PlanningResult.

Output:
- action sequence
- originating algorithm
- starting state
- expected final state
- cost
- planning metrics

A candidate plan is NOT trusted until verified.

---

## Stage 6 — Formal Verification

Purpose: independently determine whether a candidate plan is valid.

Input:
- initial/current symbolic state
- candidate plan
- action semantics
- constraints
- invariants
- goal

For each action:
1. validate action
2. check preconditions
3. apply authoritative transition
4. check invariants
5. check hard constraints
6. continue only if valid

After execution:
- check goal satisfaction

Output:
- valid/invalid
- first failure
- action index
- state before failure
- action
- violated precondition/constraint/invariant
- final state
- goal status
- trace
- verification time

The verifier must not ask an LLM whether a plan is correct.

---

## Stage 7 — Counterexample Generation

Purpose: convert verification failure into a machine-readable witness.

Input: VerificationResult.

Output:
- counterexample ID
- state snapshot
- action index
- action
- violated condition
- actual state
- expected condition
- failure category
- affected entities
- trace/evidence
- human-readable explanation

Identify the earliest meaningful violation.

Never output only "plan failed."

---

## Stage 8 — Fault Attribution

Purpose: determine the likely source of failure.

Initial taxonomy:
- PERCEPTION_ERROR
- FORMALIZATION_ERROR
- PLANNING_ERROR
- ENVIRONMENT_CHANGE
- UNKNOWN/AMBIGUOUS

Input:
- counterexample
- verification evidence
- world model
- candidate plan
- interpretation evidence
- observation history where available

Output:
- fault class
- evidence
- affected stage
- confidence/evidence strength if meaningful
- alternative explanations if relevant
- explanation

Use controlled fault injection/mutation for quantitative evaluation.

---

## Stage 9 — Repair Constraint Generation

Purpose: translate counterexample and fault evidence into an explicit repair.

Input:
- counterexample
- fault attribution
- symbolic problem

Output:
- repair type
- repair constraint/state correction
- reason
- source counterexample
- evidence
- affected search region

Possible repairs:
- forbid a violating action/object transition
- add ordering restriction
- correct a known symbolic state error when justified
- request refreshed observation for environment change

Repairs must be traceable and must not arbitrarily alter the task.

---

## Stage 10 — Replanning

Purpose: search for a new plan after applying the repair.

Input:
- modified symbolic problem
- repair constraints
- affected state
- original goal
- original hard constraints
- action library

Output:
- new CandidatePlan
- repair iteration metadata

Use local replanning when correctness is preserved; otherwise restart from the initial state.

Prevent infinite repair loops with:
- maximum iterations
- repeated-counterexample detection
- repeated-repair detection
- no-progress detection

---

## Stage 11 — Verification Again

Purpose: verify every repaired candidate exactly like the original candidate.

Loop:

```text
candidate
→ verify
→ counterexample
→ attribution
→ repair
→ replan
→ verify
```

Stop when:
- verified plan found, or
- maximum iterations reached, or
- no valid repair exists.

Final status must clearly be:
- VERIFIED
- FAILED / NO VERIFIED PLAN

---

## Stage 12 — Dynamic Environment

Purpose: handle relevant world changes after planning.

Input:
- previous symbolic state
- new observation

Output:
WorldDelta:
- added facts
- removed facts
- changed attributes
- changed relations
- affected entities

Determine whether the remaining plan is invalidated.

If relevant:
```text
new observation
→ world delta
→ invalidate old plan if necessary
→ replan
→ verify
```

Do not replan for irrelevant changes.

---

## Stage 13 — Benchmark and Evaluation

Purpose: make the research experimentally defensible.

Generate benchmark instances from symbolic ground truth.

Each instance may contain:
- initial state
- objects
- actions/domain
- constraints
- goal
- known solution where feasible
- natural-language description
- optional controlled image
- difficulty metadata
- injected-fault ground truth

Difficulty controls:
- number of objects
- state-space size
- branching factor
- planning horizon
- constraint density
- distractor actions

Baselines:
- B0: Direct neural plan generation
- B1: Neural formalization + classical planner
- B2: Planner + verifier without repair
- B3: Planner + generic regeneration
- OURS: Planner + verifier + counterexample + attribution + repair

Metrics:
- valid-plan rate
- goal success rate
- constraint violation rate
- repair success rate
- repair iterations
- nodes expanded
- planning time
- verification time
- repair time
- plan cost
- formalization accuracy
- visual accuracy
- fault-attribution accuracy
- robustness under paraphrase
- recovery after environment change

Primary research question:
Does counterexample-guided repair improve recovery from initially invalid plans compared with generic regeneration?

Required ablations:
- full system
- without verifier
- without counterexample
- without attribution
- without repair
- generic regeneration

Never fabricate results.

---

## Stage 14 — Demo Application and Integration

The application accepts:
- natural-language task
- optional image
- planner selection
- optional model/provider

The UI displays:
1. Task understanding
2. Symbolic world model
3. Search algorithm and metrics
4. Candidate plan
5. Verification result
6. If invalid:
   - first failure
   - counterexample
   - fault attribution
   - repair
   - replanning
   - verification
7. Final verified plan
8. Experiment/reproducibility information

For dynamic tasks show:
- previous observation
- new observation
- world delta
- old plan status
- new plan

The UI must not contain planning logic.

---

# 4. Required Repository Architecture

Adapt to the existing repository rather than blindly replacing it.

Conceptual target:

```text
replan-v/
├── app/
│   ├── api/
│   ├── services/
│   ├── ui/
│   └── main.*
├── core/
│   ├── world/
│   ├── predicates/
│   ├── actions/
│   ├── search/
│   ├── verification/
│   ├── counterexamples/
│   ├── attribution/
│   ├── repair/
│   └── replanning/
├── interpretation/
│   ├── llm/
│   ├── vision/
│   └── schemas/
├── benchmark/
│   ├── generator/
│   ├── mutations/
│   └── datasets/
├── evaluation/
│   ├── baselines/
│   ├── metrics/
│   ├── experiments/
│   └── reports/
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── configs/
├── docs/
└── README.*
```

Actual names must follow the existing repository.

---

# 5. Implementation Prompts

## Prompt 0 — Foundation

Inspect the entire existing repository before changing anything.

Establish or adapt the architecture for RE-PLAN-V.

Create clean module boundaries for:
- symbolic world model
- predicates
- actions
- search
- verification
- counterexamples
- fault attribution
- repair/replanning
- LLM interpretation
- vision
- benchmark
- evaluation
- UI
- configuration
- tests

Create explicit structured data contracts between stages.

Preserve working code.

Add:
- configuration
- dependency management
- logging
- error handling
- test infrastructure
- README
- minimal runnable entry point

The symbolic core must not depend on external AI APIs.

Run tests and verify the project starts.

Do not implement advanced features yet.

---

## Prompt 1 — Symbolic World Model

Implement the unified symbolic world model exactly according to Stage 3.

Support:
- typed objects
- predicates
- positive/negative facts
- initial/current states
- goals
- constraints
- invariants
- serialization
- equality/hashability
- validation

Use an extensible design.

Add deterministic tests and example domains.

---

## Prompt 2 — Actions and Transitions

Implement the authoritative action system.

Each action must define:
- typed parameters
- preconditions
- effects
- negative effects where required
- cost

Separate:
- action definition
- instantiated action
- transition.

Implement legal-action generation.

Ensure planner and verifier will use exactly the same transition semantics.

Add comprehensive tests.

---

## Prompt 3 — Search

Implement:
- BFS
- Best-First Search
- A*

Return structured metrics.

Implement a heuristic abstraction for A*.

Prevent revisiting equivalent states.

Add deterministic test domains and comparison experiments.

Do not add learned heuristics yet.

---

## Prompt 4 — Knowledge Representation and Reasoning

Implement a controlled KR&R subsystem supporting:
- predicates
- variables
- constants
- substitutions
- unification
- rules
- inference
- appropriate resolution/clause reasoning where practical

Keep it bounded and testable.

Do not build an unrestricted theorem prover.

Ensure KR&R does not silently alter physical action semantics.

---

## Prompt 5 — Formal Verification

Implement the deterministic verifier.

Check:
- action validity
- preconditions
- transitions
- invariants
- constraints
- final goals

Return detailed VerificationResult and traces.

Create valid and deliberately invalid test plans.

The verifier must be independent of LLM judgment.

---

## Prompt 6 — Counterexamples

Implement structured counterexample generation from verifier evidence.

Identify the earliest meaningful failure.

Include:
- state
- action index
- action
- violation
- expected/actual condition
- evidence
- explanation

Add serialization and replay/debug support if useful.

---

## Prompt 7 — Fault Attribution

Implement the controlled taxonomy:

PERCEPTION_ERROR
FORMALIZATION_ERROR
PLANNING_ERROR
ENVIRONMENT_CHANGE
UNKNOWN/AMBIGUOUS

Make attribution evidence-based.

Implement controlled fault injection/mutation.

Make expected-vs-predicted attribution measurable.

Do not force a classification when evidence is insufficient.

---

## Prompt 8 — Repair and Replanning

Implement the core research loop:

candidate
→ verification
→ counterexample
→ fault attribution
→ repair
→ replanning
→ verification

Create explicit Repair objects and trace every repair to evidence.

Support:
- forbidden transitions
- ordering constraints
- symbolic correction when justified
- environment refresh

Add:
- max iterations
- loop detection
- no-progress detection.

Implement comparison against generic regeneration.

---

## Prompt 9 — LLM Interpretation

Implement natural-language → structured proposal.

Use strict schemas.

Add:
- provider abstraction
- structured parsing
- validation
- retries
- error handling
- mock provider
- optional external/local providers

Never allow LLM output to bypass validation or define executable actions.

---

## Prompt 10 — Vision

Implement controlled-scene perception.

First implement deterministic OpenCV baseline.

Then create an optional VLM adapter using the same output schema.

Support:
- object detection
- attributes
- approximate positions
- spatial relations

Add ground-truth comparison and controlled visual mutations.

Keep vision optional.

---

## Prompt 11 — Dynamic Environment

Implement:
- observation comparison
- WorldDelta
- relevant-change detection
- plan invalidation
- replanning
- verification

Avoid unnecessary replanning.

Add deterministic tests for relevant and irrelevant changes.

---

## Prompt 12 — Benchmark and Evaluation

Implement procedural benchmark generation, mutation testing, baselines, metrics, ablations, reproducible experiment configuration, and result export.

Do not fabricate results.

Make the primary research question executable:

Does counterexample-guided repair improve recovery from initially invalid plans compared with generic regeneration?

Produce machine-readable logs and human-readable summaries.

---

## Prompt 13 — UI and End-to-End Integration

Integrate the entire pipeline into a polished demo.

The UI must expose:
- task understanding
- world model
- candidate plan
- verification
- counterexample
- attribution
- repair
- replanning
- final verification

Support text-only operation without external APIs.

Support optional image and LLM/VLM modes.

Keep application logic separate from UI.

Add integration and end-to-end tests.

---

# 6. Final Research Audit Prompt

After all implementation is complete, inspect the entire system as a skeptical research reviewer.

Verify:
- symbolic core is authoritative
- verifier is genuinely independent
- counterexamples are evidence-based
- fault attribution is measurable
- repairs are derived from evidence
- generic regeneration is a fair baseline
- benchmarks do not leak ground truth
- metrics are actually computed
- no results are fabricated
- experiments are reproducible
- planner/verifier semantics are identical
- UI reflects actual system state
- failure cases are visible
- external APIs are optional

Run unit, integration, end-to-end, and benchmark tests.

Identify:
- bugs
- architecture violations
- research-validity threats
- reproducibility issues
- missing experiments
- unnecessary complexity

Then fix the highest-impact issues and rerun all tests.

The final system must be suitable for:
- live demonstration
- research experiments
- ablation studies
- project report
- viva

Do not add features merely for appearance.

---

# 7. Master Prompt

Use this prompt AFTER attaching/providing this entire specification file to the coding agent.

```text
You are the lead software architect, senior AI engineer, research engineer, QA engineer, and technical project manager responsible for implementing RE-PLAN-V.

I have provided a complete RE-PLAN-V implementation specification in this file.

READ THE ENTIRE FILE FIRST.

Do not start coding until you have:
1. read the complete specification,
2. inspected the entire existing repository,
3. understood the current architecture,
4. mapped the requested architecture onto the existing repository,
5. identified dependencies between stages,
6. created an implementation plan,
7. identified any genuinely blocking ambiguities.

Do not ask me trivial questions. Make reasonable engineering decisions yourself.

Your objective is NOT merely to create a prototype that appears to work.

Your objective is to produce a:
- technically correct,
- modular,
- deterministic where appropriate,
- testable,
- reproducible,
- research-grade,
- high-accuracy,
- demo-ready,
- application-ready
implementation of RE-PLAN-V.

The central research question is:

"Can counterexample-guided fault attribution and automatic repair improve recovery from initially invalid plans compared with generic plan regeneration?"

The architecture must preserve this research question.

==================================================
NON-NEGOTIABLE ARCHITECTURAL RULES
==================================================

1. SYMBOLIC-FIRST

The symbolic system is authoritative for:
- state representation,
- action semantics,
- planning,
- verification,
- constraint enforcement,
- counterexample generation,
- fault attribution,
- repair,
- replanning.

2. NEURAL COMPONENTS ARE UNTRUSTED

LLMs and VLMs may:
- interpret language,
- interpret images,
- propose structured information.

They may NOT:
- decide plan validity,
- bypass verification,
- invent executable actions,
- override constraints,
- directly determine the final verified plan.

3. ONE AUTHORITATIVE TRANSITION SEMANTICS

Planner and verifier must use the same action definitions, preconditions, effects, and transition semantics.

Do not implement duplicate inconsistent versions.

4. EXPLICIT DATA CONTRACTS

Every stage must communicate through structured typed objects/schemas.

Avoid passing uncontrolled strings between core modules.

5. FAILURE MUST BE EXPLAINABLE

A failed plan must produce:
- first meaningful failure,
- state,
- action,
- violated condition,
- counterexample,
- fault attribution,
- repair decision,
- replanning result.

6. REPAIR MUST BE EVIDENCE-GUIDED

Do not simply ask an LLM for another plan.

Use:

candidate
→ verifier
→ counterexample
→ fault attribution
→ repair
→ replanning
→ verifier

7. NO FORCED ATTRIBUTION

If evidence is insufficient, return UNKNOWN/AMBIGUOUS.

8. NO FABRICATED RESULTS

Never invent:
- accuracy,
- success rates,
- timing,
- benchmark results,
- attribution accuracy,
- repair rates.

Only report measured results.

9. EXTERNAL AI APIS ARE OPTIONAL

The symbolic Tier-1 system must work without external APIs.

Implement mock providers for testing.

10. REPRODUCIBILITY

Experiments must support:
- fixed seeds,
- versioned configuration,
- structured logs,
- deterministic benchmark generation where practical,
- machine-readable result export.

==================================================
IMPLEMENTATION STRATEGY
==================================================

Do NOT attempt to implement everything in one uncontrolled pass.

Implement incrementally in dependency order:

Stage 0:
Repository inspection and architecture

Stage 1:
Symbolic world model

Stage 2:
Action definitions and transitions

Stage 3:
BFS / Best-First / A*

Stage 4:
KR&R

Stage 5:
Formal verification

Stage 6:
Counterexample generation

Stage 7:
Fault attribution

Stage 8:
Repair and replanning

Stage 9:
LLM interpretation

Stage 10:
Controlled vision

Stage 11:
Dynamic environment

Stage 12:
Benchmark and evaluation

Stage 13:
UI and end-to-end integration

Stage 14:
Research audit and hardening

For every stage:

IMPLEMENT
→ TEST
→ RUN
→ INSPECT
→ FIX
→ DOCUMENT
→ ONLY THEN CONTINUE.

Never assume code works because it compiles or looks correct.

==================================================
REPOSITORY INSPECTION
==================================================

Before implementation:

Inspect:
- every relevant source file,
- package/dependency configuration,
- environment configuration,
- existing tests,
- database/storage if present,
- frontend,
- backend,
- scripts,
- entry points,
- README,
- deployment configuration.

Determine:
- language,
- framework,
- package manager,
- test framework,
- current architecture,
- existing reusable components.

Preserve useful existing functionality.

Do not rewrite the repository unnecessarily.

If the existing repository already has a good architecture, adapt RE-PLAN-V to it.

==================================================
QUALITY REQUIREMENTS
==================================================

Use professional software engineering practices.

Prefer:
- strong typing where supported,
- clear interfaces,
- small cohesive modules,
- dependency inversion for external providers,
- deterministic behavior,
- structured logging,
- explicit exceptions/errors,
- validation,
- configuration management,
- unit tests,
- integration tests,
- end-to-end tests,
- reproducible experiments.

Avoid:
- giant files,
- duplicated logic,
- hidden global state,
- hard-coded API keys,
- hard-coded benchmark results,
- UI containing core planning logic,
- unnecessary dependencies,
- unnecessary microservices,
- unnecessary complexity.

Do not optimize prematurely.

First make correctness obvious.

Then optimize bottlenecks based on measurements.

==================================================
HIGH-ACCURACY REQUIREMENTS
==================================================

For every stage, identify:
- expected input,
- expected output,
- invariants,
- failure modes,
- validation strategy,
- tests.

For critical algorithms:
- test normal cases,
- edge cases,
- invalid inputs,
- empty inputs,
- impossible problems,
- repeated states,
- contradictory constraints,
- malformed actions,
- search exhaustion,
- repeated repair loops.

For neural components:
- validate every output,
- use structured schemas,
- use deterministic mocks,
- record parsing failures,
- never trust raw model output.

For vision:
- use a controlled benchmark,
- maintain ground truth,
- calculate actual metrics.

For verification:
- make the verifier deterministic,
- make failure traces reproducible.

For repair:
- preserve original constraints,
- trace every repair to evidence,
- prevent infinite loops.

==================================================
RESEARCH REQUIREMENTS
==================================================

The implementation must allow fair comparison of:

B0:
Direct neural plan generation

B1:
Neural formalization + classical planner

B2:
Planner + verifier without repair

B3:
Planner + generic regeneration

OURS:
Planner + verifier + counterexample + fault attribution + repair

Implement ablations:
- without verifier,
- without counterexample,
- without attribution,
- without repair.

The primary experiment must be executable and answer:

Does counterexample-guided repair improve recovery from initially invalid plans compared with generic regeneration?

Collect actual:
- repair success rate,
- valid-plan rate,
- constraint violation rate,
- planning time,
- verification time,
- repair time,
- nodes expanded,
- repair iterations,
- plan cost,
- fault attribution accuracy.

Do not claim a positive result before measuring it.

==================================================
APPLICATION REQUIREMENTS
==================================================

The final application must provide a coherent end-to-end user experience.

Input:
- natural language,
- optional image,
- planner choice,
- optional model/provider.

Output:
- interpreted task,
- symbolic world,
- candidate plan,
- verification,
- counterexample if failed,
- fault attribution,
- repair,
- replanning,
- final verification,
- final plan,
- metrics.

The UI must make the research mechanism visible.

The application should be usable for a live project demonstration without requiring manual manipulation of internal files.

==================================================
AUTONOMOUS DECISION MAKING
==================================================

When implementation details are unspecified:
- inspect the repository,
- choose the simplest robust architecture,
- document the decision,
- proceed.

Only ask me if the decision fundamentally changes the project scope or cannot be safely inferred.

==================================================
EXECUTION PROTOCOL
==================================================

Start by producing an implementation plan based on the entire specification and repository.

Then implement Stage 0.

After each stage:
1. run tests,
2. run representative examples,
3. inspect outputs,
4. fix failures,
5. update documentation,
6. verify that previous stages still work.

Maintain backward compatibility between stages.

Do not leave half-integrated features masquerading as complete.

==================================================
FINAL ACCEPTANCE CRITERIA
==================================================

The project is complete only when:

- symbolic planning works,
- BFS works,
- Best-First works,
- A* works,
- KR&R works within its documented scope,
- formal verification works,
- counterexamples are structured,
- fault attribution works with measurable evaluation,
- repair works,
- replanning works,
- repeated repair loops are controlled,
- LLM interpretation works through a validated schema,
- vision works in the controlled environment,
- dynamic changes can trigger replanning,
- benchmark generation works,
- baselines work,
- ablations work,
- metrics are computed from actual runs,
- experiments are reproducible,
- UI integrates the complete pipeline,
- unit tests pass,
- integration tests pass,
- end-to-end tests pass,
- representative benchmark runs successfully,
- documentation is complete,
- setup instructions work from a clean environment.

Before declaring completion, perform a final skeptical research audit.

Look specifically for:
- fake functionality,
- mocked functionality accidentally presented as real,
- duplicated action semantics,
- verifier shortcuts,
- LLM authority leaks,
- benchmark leakage,
- unfair baselines,
- fabricated metrics,
- nondeterministic tests,
- hidden dependencies,
- broken error paths,
- UI/backend inconsistencies.

Fix all high-impact issues you find.

The final deliverable must be a coherent research application, not merely a collection of independent modules.

BEGIN BY INSPECTING THE ENTIRE REPOSITORY AND THE ENTIRE SPECIFICATION FILE.
DO NOT START BY WRITING RANDOM CODE.
FIRST UNDERSTAND THE SYSTEM, THEN IMPLEMENT IT STAGE BY STAGE.
```

---

# 8. Definition of Done

A representative demo should be able to execute:

```text
User:
"Move the red box next to the blue box.
Do not move the glass."

        ↓
INTERPRETATION
        ↓
SYMBOLIC WORLD
        ↓
A* SEARCH
        ↓
CANDIDATE PLAN
        ↓
VERIFICATION
        ↓
INVALID
        ↓
COUNTEREXAMPLE
        ↓
PLANNING_ERROR
        ↓
REPAIR CONSTRAINT
        ↓
REPLANNING
        ↓
VERIFICATION
        ↓
✓ VERIFIED PLAN
```

The application must also support a case where generic regeneration and counterexample-guided repair can be compared experimentally.

The project is not complete merely because the UI displays these stages; each stage must be backed by real implementation and tests.

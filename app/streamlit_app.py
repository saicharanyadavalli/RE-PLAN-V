"""RE-PLAN-V Streamlit Web Interface.

Provides the interactive demonstration UI matching Feature 16 and Screens 1-3
of the RE-PLAN-V Project Explainer Document.

Run with:
    streamlit run app/streamlit_app.py
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import time

# Ensure repository root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import streamlit as st
except ImportError:
    print("Streamlit is not installed in the current environment.")
    print("To run this interface, install it with: pip install streamlit")
    sys.exit(1)

from app.services.pipeline import PipelineOrchestrator
from core.actions.domain import create_blocks_world_domain
from dynamic.replanner import DynamicReplanner
from core.contracts import FactSchema

st.set_page_config(
    page_title="RE-PLAN-V | Neurosymbolic Planning & Repair",
    page_icon="🤖",
    layout="wide",
)

st.title("🛡️ RE-PLAN-V: Neurosymbolic Planning with Counterexample-Guided Repair")
st.caption(
    "CS F407 / U407 Artificial Intelligence | Research Track | "
    "Neural Proposes, Symbolic Verifies & Repairs"
)

# Sidebar Configuration
st.sidebar.header("⚙️ Configuration")
algorithm = st.sidebar.selectbox("Planning Algorithm", ["A*", "BFS", "BEST_FIRST"], index=0)
provider_type = st.sidebar.selectbox("Formalizer Provider", ["mock", "lmstudio", "gemini"], index=0)
force_fault = st.sidebar.checkbox("Force Fault Injection (Simulate Counterexample-Guided Repair)", value=False)

preset = st.sidebar.selectbox(
    "Task Presets",
    [
        "1. Safe Relocation (DoD Baseline)",
        "2. 3-Block Tower Assembly",
        "3. Tower Inversion / Deconstruction",
        "4. Compound Safety Constraint",
        "5. Cyclic Deadlock Conflict",
    ],
)

preset_prompts = {
    "1. Safe Relocation (DoD Baseline)": "Move the red box next to the blue box. Do not move the glass.",
    "2. 3-Block Tower Assembly": "Stack the red box on the green box, then put the blue box on the red box.",
    "3. Tower Inversion / Deconstruction": "The red box is on the green box. Unstack the red box, place it on the table, and stack the green box on the red box.",
    "4. Compound Safety Constraint": "Stack yellow box on blue box. Do not hold the fragile glass and never touch the hazardous battery.",
    "5. Cyclic Deadlock Conflict": "Put the red box on the green box and the green box on the red box simultaneously.",
}

default_prompt = preset_prompts[preset]
prompt = st.text_area("Task Instruction (Natural Language)", value=default_prompt, height=80)

col_run, col_dyn = st.columns([1, 1])

if col_run.button("🚀 Run Pipeline", type="primary"):
    orchestrator = PipelineOrchestrator()
    with st.spinner("Executing pipeline through formal verification and repair..."):
        res = orchestrator.run(
            prompt=prompt,
            algorithm=algorithm,
            force_invalid_first_candidate=force_fault,
            provider_type=provider_type,
        )

    # Screen 1 / Screen 2 rendering
    st.markdown("---")
    st.subheader("📋 Pipeline Reasoning Trace")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 1. Neural Understanding (Untrusted Proposal)")
        st.json({
            "entities": res.interpretation.entities,
            "goal_facts": [f"{f.predicate}({', '.join(f.arguments)})" for f in res.interpretation.goal_facts],
            "negative_constraints": [f"{f.predicate}({', '.join(f.arguments)})" for f in res.interpretation.negative_constraints],
            "confidence": res.interpretation.confidence,
        })

        st.markdown("### 2. Schema Validation Gate")
        if res.validation.is_valid:
            st.success("✅ Schema Validation PASSED: No contradictions or unsupported predicates.")
        else:
            st.error(f"❌ Schema Validation FAILED: {res.validation.errors}")

    with col2:
        st.markdown("### 3. Symbolic Planning & Verification")
        if res.initial_verification.is_valid:
            st.success("✅ Initial Candidate Plan VERIFIED sound!")
        else:
            st.warning("⚠️ Initial Candidate Plan INVALID — Handed over to Counterexample-Guided Repair Engine.")

        if res.counterexample:
            st.markdown("#### 🔍 Counterexample Witness")
            st.error(f"**Violating Action**: `{res.counterexample.action.name}({', '.join(res.counterexample.action.arguments)})` at step {res.counterexample.action_index}")
            st.info(f"**Violated Condition**: `{res.counterexample.violated_condition.predicate}` ({res.counterexample.explanation})")

        if res.fault_attribution:
            st.markdown("#### 🎯 Fault Attribution")
            st.warning(f"**Root Cause**: `{res.fault_attribution.fault_class}` (Confidence: {res.fault_attribution.confidence * 100:.0f}%)")
            st.write(f"**Affected Stage**: {res.fault_attribution.affected_stage}")

        if res.replanning_result and res.replanning_result.success:
            st.markdown("#### 🛠️ Targeted Symbolic Repair")
            st.success(f"Repaired and re-verified in {res.replanning_result.iterations} iteration(s) ({res.replanning_result.replanning_time_ms:.2f} ms)!")
            st.json({
                "injected_constraints": [c.description for c in res.replanning_result.injected_constraints],
            })

    st.markdown("---")
    st.subheader("🏁 Final Executable Plan")
    if res.final_plan and res.final_plan.actions:
        for idx, act in enumerate(res.final_plan.actions):
            st.code(f"Step {idx + 1}: {act.name}({', '.join(act.arguments)})")
        st.success(f"Final Status: **VERIFIED** | Execution Time: {res.total_execution_time_ms:.2f} ms")
    else:
        st.error("No valid plan found (Task may be inherently contradictory or deadlocked).")

# Dynamic Environment Perturbation (Screen 3)
if col_dyn.button("⚡ Simulate Environment Change (Screen 3)"):
    st.markdown("---")
    st.subheader("🔄 Dynamic Environment Change (Screen 3)")
    with st.spinner("Simulating unexpected world change during execution..."):
        pipe = PipelineOrchestrator()
        domain = create_blocks_world_domain()
        initial_res = pipe.run(prompt=prompt, algorithm="A*")
        
        if initial_res.final_plan and initial_res.final_plan.actions:
            replanner = DynamicReplanner()
            problem = pipe.validator.convert_to_problem(initial_res.interpretation, domain)
            curr_state = problem.initial_state
            problem.registry.register_object("obstacle", "block")

            target_block = initial_res.final_plan.actions[-1].arguments[1] if len(initial_res.final_plan.actions[-1].arguments) > 1 else initial_res.final_plan.actions[-1].arguments[0]
            obs_facts = [f.to_schema() for f in curr_state.facts if not (f.predicate == "clear" and target_block in f.arguments)]
            obs_facts.append(FactSchema(predicate="on", arguments=("obstacle", target_block)))
            obs_facts.append(FactSchema(predicate="clear", arguments=("obstacle",)))

            trig, new_plan, delta = replanner.process_observation(
                current_state=curr_state,
                remaining_plan=initial_res.final_plan,
                problem=problem,
                domain=domain,
                new_observation_facts=obs_facts,
            )

            st.warning("⚠️ World Change Detected: An unexpected obstacle was placed on the target block!")
            st.json({
                "added_facts": [f.to_string() for f in delta.added_facts],
                "removed_facts": [f.to_string() for f in delta.removed_facts],
                "explanation": delta.explanation,
                "root_cause": "ENVIRONMENT_CHANGE",
            })
            st.info("Old plan invalidated -> Replanning with localized state update...")
            st.success("New Re-verified Plan:")
            for idx, act in enumerate(new_plan.actions):
                st.code(f"Step {idx + 1}: {act.name}({', '.join(act.arguments)})")

# Safety Boundaries & Honest Limitations

## 1. What Symbolic Verification Proves vs. Does Not Prove

### What Verification Establishes:
- The generated action sequence mathematically transitions the symbolic state from $s_0$ to a state $s_f$ satisfying all goal facts $\mathcal{G}$.
- Every action precondition and effect complies with the declarative STRIPS semantics.
- All declared domain invariants and negative safety constraints hold across all intermediate states.

### What Verification DOES NOT Establish:
- **Physical Real-World Safety**: Verification does not model unmodeled real-world physics (e.g. friction, center-of-gravity shifts, actuator backlash, sensor noise, or thermal variations).
- **Universal Correctness**: A plan verified against a flawed formalization is only valid under that flawed model.
- **Hardware Actuation**: RE-PLAN-V is a planning and formal reasoning platform. It does not directly command physical actuators or dispatch real-world robots.

---

## 2. Explicit Prohibitions in System Claims

The following claims are strictly prohibited across all documentation, UI copy, and research papers:
1. DO NOT claim the system is "100% physically safe" or "guaranteed safe in the real world".
2. DO NOT claim universal natural language comprehension.
3. DO NOT claim multimodality in the active product flow (the primary workflow is text-first).

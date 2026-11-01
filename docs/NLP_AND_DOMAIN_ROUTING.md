# Natural Language Processing & Domain Routing

## 1. Text-First Design Philosophy

The primary user flow for RE-PLAN-V is text-first: users supply natural language instructions through a prominent textbox in Mission Control. Vision and image detection are completely decoupled from the primary flow to prevent vision errors from contaminating symbolic reasoning.

---

## 2. The Domain Router (`interpretation/router.py`)

The Domain Router categorizes natural language instructions into one of four deterministic outcomes:

| Outcome | Condition | System Action |
| :--- | :--- | :--- |
| `SUPPORTED` | Prompt aligns with a registered domain and provides complete entities. | Compiles into a `StructuredProposal` and forwards to symbolic validation. |
| `NEEDS_CLARIFICATION` | Prompt references ambiguous entities or omits critical target locations. | Halts pipeline and requests explicit clarification from the user. **No silent facts are invented.** |
| `UNSUPPORTED` | Prompt describes physical or algorithmic tasks outside registered domain boundaries. | Issues an explicit rejection explaining why the task is outside scope. |
| `INVALID_PROPOSAL` | Proposal contains contradictory predicates or invalid type assignments. | Triggers validation backtrack loop. |

---

## 3. Negative Constraints & Negation Preservation

RE-PLAN-V strictly preserves negative constraints:
- Natural language phrases like `"do not move the glass"`, `"do not touch block X"`, or `"avoid restricted aisle 3"` are parsed directly into `FactSchema` negative constraints.
- Negative constraints are checked during state transitions and during plan verification. Any candidate action that manipulates or violates a protected entity is immediately intercepted and triggers counterexample generation.

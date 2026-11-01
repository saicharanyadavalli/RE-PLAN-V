# Model B: Complete Reachable-State Graph Explorer

## 1. Mathematical & Engineering Foundation

The State-Space Graph in RE-PLAN-V represents the transition system induced by a symbolic planning problem $\langle \mathcal{S}, \mathcal{A}, s_0, \mathcal{G} \rangle$:
- **Node $u \in \mathcal{V}$**: A unique, semantically distinct symbolic state $s$. A node represents a set of ground facts, NOT a traversal path.
- **Directed Edge $(u, v) \in \mathcal{E}$**: A valid ground action transition $a \in \mathcal{A}$ such that $\text{pre}(a) \subseteq s(u)$, $s(v) = (s(u) \setminus \text{del}(a)) \cup \text{add}(a)$, and $s(v)$ satisfies all domain invariants.
- **Cycles**: If a sequence of actions returns to a previously visited semantic state, an edge is created back to the existing node. Cycles do NOT spawn duplicate nodes or cause infinite expansion.
- **Dead Ends**: States $s$ where no valid actions are applicable, yet goal conditions are not satisfied.
- **Goal States**: States $s$ where $\mathcal{G} \subseteq s$.

---

## 2. Graph Enumeration Algorithm

The enumeration is executed by `CompleteReachableGraphEnumerator`:
```text
Algorithm CompleteReachableGraph(problem, domain, budget):
  1. s0 = problem.initial_state
  2. hash0 = domain.canonical_state_hash(s0)
  3. node0 = create_node(id=s0, hash=hash0, depth=0)
  4. V = {hash0: node0}, E = [], queue = [s0]
  5. While queue is not empty:
       If |V| >= budget.max_nodes or time_elapsed() >= budget.timeout:
         Return Graph(V, E, is_complete=False, reason="MAX_NODES_EXCEEDED" | "TIMEOUT")
       s = queue.pop()
       actions = domain.get_applicable_actions(s, problem.registry)
       For each action in actions:
         s_next = domain.apply_action(s, action)
         valid, msg = domain.check_invariants(s_next)
         If not valid: continue
         hash_next = domain.canonical_state_hash(s_next)
         If hash_next not in V:
           V[hash_next] = create_node(s_next)
           queue.append(s_next)
         E.append(create_edge(source=V[s], target=V[s_next], action=action))
  6. Return Graph(V, E, is_complete=True)
```

---

## 3. Honest Completeness & Truncation Handling

Under no circumstances does RE-PLAN-V claim a graph is complete if budget limits were reached:
- When queue empties naturally: `is_complete = True`, `truncation_reason = None`.
- When `max_nodes` or `timeout` is reached: `is_complete = False`, `truncation_reason = "MAX_NODES_EXCEEDED" | "TIMEOUT"`.
- Nodes at the exploration frontier are marked with `is_truncated_boundary = True` and styled with an amber halo in the UI.

---

## 4. Cytoscape and WebSocket Streaming

The graph data is streamed over WebSockets in batches:
- `GRAPH_NODE_BATCH`: Batches of up to 30 nodes with pre-computed summaries.
- `GRAPH_EDGE_BATCH`: Batches of up to 50 edges.
- Node details (full list of facts, incoming actions, outgoing actions) are inspectable on-demand in the frontend State Space Explorer.

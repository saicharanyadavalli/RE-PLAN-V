# REST API & WebSocket Streaming Protocol Specification

## 1. REST Endpoints

### `GET /api/domains`
Returns metadata, action schemas, predicate definitions, complexity ratings, and example prompts for all 6 registered canonical domains.

### `POST /api/graph/enumerate`
Computes the complete reachable state-space graph for a given domain and prompt without executing a full search or replanning loop.

**Request Schema:**
```json
{
  "domain_id": "blocks_world",
  "prompt": "Stack the red box on the blue box.",
  "max_nodes": 300,
  "max_edges": 1000,
  "timeout_seconds": 5.0
}
```

**Response:** Cytoscape-formatted JSON containing `elements` (nodes and edges) and `stats` (node counts, edge counts, dead ends, goal counts, and completeness status).

---

## 2. WebSocket Protocol (`/ws/pipeline`)

Clients connect to `ws://127.0.0.1:8080/ws/pipeline` and transmit a `PipelineRunRequest`.

### Streaming Event Sequence
1. `PIPELINE_STARTED`: Execution initiated.
2. `DOMAIN_SELECTED`: NLP router assigns domain.
3. `INTERPRETATION_COMPLETED`: Formalized symbolic proposal validated.
4. `GRAPH_ENUMERATION_STARTED`: Model B exploration begins.
5. `GRAPH_NODE_BATCH`: Chunks of reachable state nodes (batches of 30).
6. `GRAPH_EDGE_BATCH`: Chunks of valid action transitions (batches of 50).
7. `GRAPH_ENUMERATION_COMPLETED` / `GRAPH_ENUMERATION_TRUNCATED`: State-space status and statistics summary.
8. `SEARCH_COMPLETED`: Candidate action plan generated.
9. `VERIFICATION_STEP` / `VERIFICATION_RESULT`: Plan verification status.
10. `COUNTEREXAMPLE_EXTRACTED` & `REPAIR_INJECTED`: (If fault simulated/encountered) Witness details and CEGIS repair constraints.
11. `FINAL_VERIFICATION`: Verified repaired plan.
12. `PIPELINE_FINISHED`: Execution completed.

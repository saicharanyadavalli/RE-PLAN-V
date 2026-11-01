export interface FactSchema {
  predicate: string;
  arguments: string[];
}

export interface GroundActionSchema {
  name: string;
  arguments: string[];
  cost?: number;
}

export interface GraphNode {
  id: string;
  node_id?: string;
  state_hash?: string;
  depth: number;
  is_initial: boolean;
  is_goal: boolean;
  is_dead_end: boolean;
  is_boundary?: boolean;
  is_truncated_boundary: boolean;
  facts: FactSchema[] | string[];
  facts_summary: string[];
  summary?: string;
  incoming_edges_count?: number;
  outgoing_edges_count?: number;
}

export interface GraphEdge {
  id?: string;
  edge_id?: string;
  source: string;
  source_id?: string;
  target: string;
  target_id?: string;
  action_name: string;
  action_args: string[];
  action_label?: string;
  label?: string;
  cost: number;
  is_cycle?: boolean;
  is_plan_edge?: boolean;
  is_repaired_edge?: boolean;
}

export interface GraphStats {
  total_nodes: number;
  total_edges: number;
  max_depth?: number;
  max_depth_reached: number;
  goal_node_ids: string[];
  dead_end_node_ids: string[];
  is_complete: boolean;
  truncation_reason?: string | null;
  enumeration_time_ms: number;
  duplicate_states_pruned?: number;
  cycles_detected?: number;
}

export interface ReachableStateGraph {
  elements: Array<{ data: Record<string, any> }>;
  stats: GraphStats;
}

export interface DomainMetadata {
  domain_id: string;
  display_name: string;
  description: string;
  complexity_rating: string;
  entity_types: string[];
  action_names: string[];
  predicate_names: string[];
  example_tasks: string[];
  supported_features: string[];
  unsupported_features: string[];
}

export interface RoutingResult {
  outcome: "SUPPORTED" | "NEEDS_CLARIFICATION" | "UNSUPPORTED" | "INVALID_PROPOSAL";
  selected_domain_id?: string;
  domain_confidence: number;
  clarification_question?: string;
  explanation: string;
  entities?: Record<string, string>;
  initial_facts?: FactSchema[];
  goal_facts?: FactSchema[];
  negative_constraints?: FactSchema[];
}

export interface CounterexampleWitness {
  counterexample_id?: string;
  step_index?: number;
  action_index?: number;
  failed_action?: GroundActionSchema;
  offending_action?: GroundActionSchema;
  violated_condition?: string | FactSchema;
  failure_category?: string;
  affected_entities?: string[];
  state_snapshot?: any;
  explanation: string;
}

export interface FaultAttribution {
  fault_class: "PERCEPTION_ERROR" | "FORMALIZATION_ERROR" | "PLANNING_ERROR" | "ENVIRONMENT_CHANGE" | "UNKNOWN_AMBIGUOUS";
  affected_stage: string;
  confidence: number;
  explanation?: string;
}

export interface RepairConstraint {
  repair_id?: string;
  repair_type?: string;
  type?: string;
  description: string;
  forbidden_action?: GroundActionSchema;
  action_name?: string;
  arguments?: string[];
}

export type PipelineStage =
  | "IDLE"
  | "PIPELINE_STARTED"
  | "DOMAIN_SELECTED"
  | "CLARIFICATION_REQUIRED"
  | "TASK_UNSUPPORTED"
  | "INTERPRETATION_STARTED"
  | "INTERPRETATION_COMPLETED"
  | "VALIDATION_RESULT"
  | "VALIDATION_FAILED"
  | "BACKTRACK"
  | "GRAPH_ENUMERATION_STARTED"
  | "GRAPH_NODE_BATCH"
  | "GRAPH_EDGE_BATCH"
  | "GRAPH_ENUMERATION_COMPLETED"
  | "GRAPH_ENUMERATION_TRUNCATED"
  | "SEARCH_STARTED"
  | "SEARCH_NODE_EXPANDED"
  | "SEARCH_COMPLETED"
  | "PLANNER_CASCADE"
  | "PLANNING_FAILED"
  | "VERIFICATION_STEP"
  | "VERIFICATION_FAILED"
  | "VERIFICATION_RESULT"
  | "COUNTEREXAMPLE_EXTRACTED"
  | "ATTRIBUTION_CLASSIFIED"
  | "REPAIR_INJECTED"
  | "REPAIR_FAILED"
  | "REPLAN_COMPLETED"
  | "FINAL_VERIFICATION"
  | "PIPELINE_FINISHED"
  | "ERROR";

export interface StageAttemptRecord {
  stage: string;
  attempt: number;
  status: string;
  provider_used?: string;
  duration_ms: number;
  error?: string;
  recovery_action?: string;
  details?: Record<string, any>;
}

export interface PipelineDecisionTrace {
  total_attempts: number;
  interpretation_attempts: number;
  validation_retries: number;
  planner_cascades: number;
  backtracks: number;
  final_provider?: string;
  final_algorithm?: string;
  stage_trace?: StageAttemptRecord[];
  recovery_path?: string[];
}

export interface PipelineStreamEvent {
  stage: PipelineStage;
  timestamp: number;
  message: string;
  data: Record<string, any>;
}

export interface PipelineRunRequest {
  prompt: string;
  algorithm: string;
  domain_id?: string;
  force_fault: boolean;
  provider_type: string;
  llm_model?: string;
  enumerate_graph?: boolean;
  max_nodes?: number;
  max_edges?: number;
  graph_timeout?: number;
}

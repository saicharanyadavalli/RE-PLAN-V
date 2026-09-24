export interface FactSchema {
  predicate: string;
  arguments: string[];
}

export interface GroundActionSchema {
  name: string;
  arguments: string[];
  cost?: number;
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
  | "INTERPRETATION_STARTED"
  | "INTERPRETATION_COMPLETED"
  | "VALIDATION_RESULT"
  | "VALIDATION_FAILED"
  | "BACKTRACK"
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
  force_fault: boolean;
  provider_type: string;
  llm_model?: string;
}

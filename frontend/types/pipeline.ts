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
  step_index: number;
  failed_action: GroundActionSchema;
  violated_condition: string;
  state_snapshot?: FactSchema[];
  explanation: string;
}

export interface FaultAttribution {
  fault_class: "PERCEPTION_ERROR" | "FORMALIZATION_ERROR" | "PLANNING_ERROR" | "ENVIRONMENT_CHANGE" | "UNKNOWN_AMBIGUOUS";
  affected_stage: string;
  confidence: number;
  explanation?: string;
}

export interface RepairConstraint {
  type: string;
  action_name: string;
  arguments: string[];
  description: string;
}

export type PipelineStage =
  | "IDLE"
  | "PIPELINE_STARTED"
  | "INTERPRETATION_STARTED"
  | "INTERPRETATION_COMPLETED"
  | "VALIDATION_RESULT"
  | "SEARCH_STARTED"
  | "SEARCH_NODE_EXPANDED"
  | "SEARCH_COMPLETED"
  | "VERIFICATION_STEP"
  | "VERIFICATION_FAILED"
  | "VERIFICATION_RESULT"
  | "COUNTEREXAMPLE_EXTRACTED"
  | "ATTRIBUTION_CLASSIFIED"
  | "REPAIR_INJECTED"
  | "REPLAN_COMPLETED"
  | "FINAL_VERIFICATION"
  | "PIPELINE_FINISHED"
  | "ERROR";

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

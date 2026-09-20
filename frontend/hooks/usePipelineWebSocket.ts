"use client";

import { useState, useCallback, useRef } from "react";
import {
  PipelineStreamEvent,
  PipelineRunRequest,
  CounterexampleWitness,
  FaultAttribution,
  GroundActionSchema,
  RepairConstraint,
} from "../types/pipeline";

export interface PipelineAccumulatedState {
  prompt: string;
  entities: Record<string, string>;
  initialFacts: any[];
  goalFacts: any[];
  negativeConstraints: any[];
  isSchemaValid: boolean | null;
  candidatePlan: GroundActionSchema[];
  candidateCost: number;
  initialVerificationPassed: boolean | null;
  verificationFailureMessage?: string;
  counterexample?: CounterexampleWitness;
  attribution?: FaultAttribution;
  repairsApplied?: RepairConstraint[];
  finalPlan: GroundActionSchema[];
  isFinalVerified: boolean | null;
  executionTimeMs: number;
}

const initialState: PipelineAccumulatedState = {
  prompt: "",
  entities: {},
  initialFacts: [],
  goalFacts: [],
  negativeConstraints: [],
  isSchemaValid: null,
  candidatePlan: [],
  candidateCost: 0,
  initialVerificationPassed: null,
  finalPlan: [],
  isFinalVerified: null,
  executionTimeMs: 0,
};

export function usePipelineWebSocket(backendUrl: string = "http://127.0.0.1:8000") {
  const [isStreaming, setIsStreaming] = useState(false);
  const [events, setEvents] = useState<PipelineStreamEvent[]>([]);
  const [state, setState] = useState<PipelineAccumulatedState>(initialState);
  const [error, setError] = useState<string | null>(null);
  const socketRef = useRef<WebSocket | null>(null);

  const reset = useCallback(() => {
    setEvents([]);
    setState(initialState);
    setError(null);
    setIsStreaming(false);
  }, []);

  const runPipeline = useCallback(
    (req: PipelineRunRequest) => {
      reset();
      setIsStreaming(true);
      setState((prev) => ({ ...prev, prompt: req.prompt }));

      const wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      // Derive host from window or fallback to default backend
      const host = window.location.hostname || "127.0.0.1";
      const wsUrl = `${wsProtocol}//${host}:8000/ws/pipeline`;

      try {
        const ws = new WebSocket(wsUrl);
        socketRef.current = ws;

        ws.onopen = () => {
          ws.send(JSON.stringify(req));
        };

        ws.onmessage = (event) => {
          try {
            const data: PipelineStreamEvent = JSON.parse(event.data);
            setEvents((prev) => [...prev, data]);

            // Update accumulated state stage by stage
            if (data.stage === "INTERPRETATION_COMPLETED") {
              setState((prev) => ({
                ...prev,
                entities: data.data.entities || {},
                goalFacts: data.data.goal_facts || [],
                initialFacts: data.data.initial_facts || [],
                negativeConstraints: data.data.negative_constraints || [],
                isSchemaValid: data.data.is_valid,
              }));
            } else if (data.stage === "SEARCH_COMPLETED") {
              setState((prev) => ({
                ...prev,
                candidatePlan: data.data.actions || [],
                candidateCost: data.data.cost || 0,
              }));
            } else if (data.stage === "VERIFICATION_RESULT") {
              setState((prev) => ({
                ...prev,
                initialVerificationPassed: data.data.is_valid,
              }));
            } else if (data.stage === "VERIFICATION_FAILED") {
              setState((prev) => ({
                ...prev,
                initialVerificationPassed: false,
                verificationFailureMessage: data.data.explanation,
              }));
            } else if (data.stage === "COUNTEREXAMPLE_EXTRACTED") {
              setState((prev) => ({
                ...prev,
                counterexample: data.data.witness,
              }));
            } else if (data.stage === "ATTRIBUTION_CLASSIFIED") {
              setState((prev) => ({
                ...prev,
                attribution: {
                  fault_class: data.data.fault_class,
                  affected_stage: data.data.affected_stage,
                  confidence: data.data.confidence,
                },
              }));
            } else if (data.stage === "REPAIR_INJECTED") {
              setState((prev) => ({
                ...prev,
                repairsApplied: data.data.repairs_applied || [],
              }));
            } else if (data.stage === "FINAL_VERIFICATION") {
              setState((prev) => ({
                ...prev,
                finalPlan: data.data.final_plan || [],
                isFinalVerified: data.data.is_valid,
                executionTimeMs: data.data.execution_time_ms || 0,
              }));
            } else if (data.stage === "PIPELINE_FINISHED" || data.stage === "ERROR") {
              setIsStreaming(false);
              ws.close();
            }
          } catch (e: any) {
            console.error("Failed to parse WebSocket message:", e);
          }
        };

        ws.onerror = async () => {
          console.warn("WebSocket error; falling back to REST endpoint /api/pipeline/run");
          // Fallback to REST API
          try {
            const resp = await fetch(`${backendUrl}/api/pipeline/run`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                prompt: req.prompt,
                algorithm: req.algorithm,
                force_invalid_first_candidate: req.force_fault,
                provider_type: req.provider_type,
                llm_model: req.llm_model,
              }),
            });
            if (!resp.ok) throw new Error(await resp.text());
            const json = await resp.json();

            setState({
              prompt: req.prompt,
              entities: json.interpretation?.entities || {},
              initialFacts: json.interpretation?.initial_facts || [],
              goalFacts: json.interpretation?.goal_facts || [],
              negativeConstraints: json.interpretation?.negative_constraints || [],
              isSchemaValid: json.validation?.is_valid ?? true,
              candidatePlan: json.candidate_plan?.actions || [],
              candidateCost: json.candidate_plan?.total_cost || 0,
              initialVerificationPassed: json.initial_verification?.is_valid,
              verificationFailureMessage: json.initial_verification?.explanation,
              counterexample: json.counterexample,
              attribution: json.fault_attribution,
              repairsApplied: json.repairs_applied,
              finalPlan: json.final_plan?.actions || [],
              isFinalVerified: json.final_verification?.is_valid,
              executionTimeMs: json.total_execution_time_ms || 0,
            });
          } catch (err: any) {
            setError(err.message || "Failed to execute pipeline via REST fallback");
          } finally {
            setIsStreaming(false);
          }
        };
      } catch (err: any) {
        setError(err.message || "WebSocket initialization error");
        setIsStreaming(false);
      }
    },
    [backendUrl, reset]
  );

  return {
    isStreaming,
    events,
    state,
    error,
    runPipeline,
    reset,
  };
}
